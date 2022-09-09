#!/usr/bin/env python3
import sys
import os
import argparse
import json
import glob
import subprocess
from queue import SimpleQueue
from threading import Thread
from select import select
from typing import List, Tuple


COL_PY = os.path.join(os.path.dirname(__file__), 'col.py')

def encode_env(type_name, value):
    if type_name == 'bool':
        return '1' if value else ''
    else:
        return str(value)


def list_filters(path):
    for filename in glob.glob(path, recursive=True):
        try:
            with open(filename) as fh:
                defaults = {
                    "name": os.path.splitext(os.path.basename(filename))[0],
                    "basedir": os.path.dirname(filename)
                }
                yield {**defaults, **json.load(fh)}
        except Exception as e:
            print(f"Could not parse {filename}: {e}", file=sys.stderr)


def babysit_child(child, name, print_queue, ctrl_queue):
    prefix = f'[{name}] '.encode()

    for line in child.stderr:
        print_queue.put(prefix + line)

    child.wait()

    print_queue.put(f'[run.py] {name} exited with status code {child.returncode}\n'.encode())

    ctrl_queue.put(child.returncode)


def print_lines(queue, fout):
    while True:
        line = queue.get()
        if line is None:
            break
        fout.buffer.write(line)


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('--filters', '-f', type=str, default='./filters')
    parser.add_argument('--input', '-i', type=argparse.FileType('rb'))
    parser.add_argument('--output', '-o', type=argparse.FileType('wb'), default=sys.stdout.buffer)
    parser.add_argument('--basedir', '-b', type=str, help='Directory to look for data files when -i is not used')
    parser.add_argument('pipeline', metavar='PIPELINE', type=argparse.FileType('r'))
    parser.add_argument('languages', metavar='LANG', type=str, nargs=2)

    args = parser.parse_args(argv)

    # default search path for the data files is next to the configuration file
    # which is the default save location for empty-train.
    if not args.basedir:
        args.basedir = os.path.dirname(args.pipeline.name)

    pipeline = json.load(args.pipeline)

    # load all filter definitions (we need to, to get their name)
    FILTERS = {
        definition['name']: definition
        for definition in list_filters(os.path.join(args.filters, '*.json'))
    }

    # Assert we have all filters we need
    assert set(step['filter'] for step in pipeline['filters']) - set(FILTERS.keys()) == set()

    children: List[Popen] = []

    babysitters: List[Thread] = []

    print_queue = SimpleQueue() # type: SimpleQueue[Optional[bytes]]

    ctrl_queue = SimpleQueue() # type: SimpleQueue[int]

    # If we're not reading from stdin, read from files and paste them together
    if not args.input:
        for filename in pipeline['files']:
            child = subprocess.Popen(
                ['gzip', '-cd', filename],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=args.basedir)

            children.append(child)

            thread = Thread(target=babysit_child, args=[child, f'ungzip {filename}', print_queue, ctrl_queue])
            thread.start()
            babysitters.append(thread)

        child = subprocess.Popen(
            ['paste'] + [f'/dev/fd/{child.stdout.fileno()}' for child in children],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            pass_fds=[child.stdout.fileno() for child in children])

        thread = Thread(target=babysit_child, args=[child, 'paste', print_queue, ctrl_queue])
        thread.start()
        babysitters.append(thread)

        children.append(child)

    # Start child processes, each reading the output from the previous sibling
    for i, step in enumerate(pipeline['filters']):
        filter_definition = FILTERS[step['filter']]
        
        filter_env = os.environ.copy()
        for name, props in filter_definition['parameters'].items():
            filter_env[name] = encode_env(props['type'], step['parameters'][name])

        if filter_definition['type'] == 'bilingual':
            command = filter_definition['command']
        elif filter_definition['type'] == 'monolingual':
            column = args.languages.index(step['language'])
            command = f'{COL_PY} {column} {filter_definition["command"]}'
        else:
            raise NotImplementedError()

        is_last_step = i + 1 == len(pipeline['filters'])

        child = subprocess.Popen(command,
            stdin=args.input if len(children) == 0 else children[-1].stdout,
            stdout=args.output if is_last_step else subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=filter_env,
            cwd=filter_definition['basedir'],
            shell=True)

        thread = Thread(target=babysit_child, args=[child, f'step {i}', print_queue, ctrl_queue])
        thread.start()
        babysitters.append(thread)

        children.append(child)

    print_thread = Thread(target=print_lines, args=[print_queue, sys.stderr])
    print_thread.start()

    # Wait for the children to exit, and depending on their retval exit early
    running_children = len(children)

    try:
        while running_children > 0:
            retval = ctrl_queue.get()
            running_children -= 1

            # Early exit when a process errored out
            if retval != 0:
                break
    except KeyboardInterrupt:
        print('[run.py] KeyboardInterrupt', file=sys.stderr)
        pass

    # Kill all the processes that are still alive
    for child in children:
        if child.returncode is None:
            child.kill()

    # Wait for the babysitters to exit, which happens when their process stops
    for thread in babysitters:
        thread.join()

    # Tell print thread to stop (there are no more babysitters now to produce printable stuff)
    print_queue.put(None)
    print_thread.join()

    # If we didn't cleanly exit all processes, we err as well
    if running_children > 0:
        sys.exit(1)

if __name__ == '__main__':
    main(sys.argv[1:])
