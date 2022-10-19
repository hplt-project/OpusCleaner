#!/usr/bin/env python3
"""Stand-alone filter pipeline runner. Executes all of the filters defined in
a dataset filtering pipeline created by empty-train in their own process and
links them together through pipes. Can read from stdin but by default reads
the dataset from the same folder as the pipeline configuration file.
"""
import sys
import os
import argparse
import json
import signal
from shlex import quote
from glob import glob
from queue import SimpleQueue
from threading import Thread
from subprocess import Popen, PIPE
from typing import List, Any, BinaryIO, Optional, TypeVar, Iterable


COL_PY = os.path.join(os.path.dirname(__file__), 'col.py')


T = TypeVar("T")

def none_throws(optional: Optional[T], message: str = "Unexpected `None`") -> T:
    if optional is None:
        raise AssertionError(message)
    return optional


def encode_env(type_name: str, value: Any) -> str:
    if type_name == 'bool':
        return '1' if value else ''
    else:
        return str(value)


def list_filters(path: str) -> Iterable[dict]:
    """Scans all files matching the path pattern and attempts to parse them as
    filter json definitions.
    """
    for filename in glob(path, recursive=True):
        try:
            with open(filename) as fh:
                defaults = {
                    "name": os.path.splitext(os.path.basename(filename))[0],
                    "basedir": os.path.dirname(filename)
                }
                yield {**defaults, **json.load(fh)}
        except Exception as e:
            print(f"Could not parse {filename}: {e}", file=sys.stderr)


def babysit_child(n: int, child: Popen, name: str, print_queue: SimpleQueue, ctrl_queue: SimpleQueue):
    """Thread that looks after a child process and passes (and prefixes) all of
    its stderr to a queue. It will tell the parent thread about the end of the
    child through the ctrl_queue.
    """
    prefix = f'[{name}] '.encode()

    for line in none_throws(child.stderr):
        print_queue.put(prefix + line)

    child.wait()

    print_queue.put(f'[run.py] {name} exited with status code {child.returncode}\n'.encode())

    ctrl_queue.put((n, child.returncode))


def print_lines(queue: SimpleQueue, fout: BinaryIO):
    """Thread that prints stderr lines from all the children to stderr in an
    orderly fashion.
    """
    while True:
        line = queue.get()
        if line is None:
            break
        fout.write(line)

        # Since we're writing stderr, we flush after each line to make it more
        # useful for debugging
        fout.flush()


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('--filters', '-f', type=str, default='./filters')
    parser.add_argument('--input', '-i', type=argparse.FileType('rb'))
    parser.add_argument('--output', '-o', type=argparse.FileType('wb'), default=sys.stdout.buffer)
    parser.add_argument('--basedir', '-b', type=str, help='Directory to look for data files when -i is not used')
    parser.add_argument('--tee', action='store_true', help='Write output after each step to a separate file')
    parser.add_argument('pipeline', metavar='PIPELINE', type=argparse.FileType('r'))
    parser.add_argument('languages', metavar='LANG', type=str, nargs='*')

    args = parser.parse_args(argv)

    # default search path for the data files is next to the configuration file
    # which is the default save location for empty-train.
    if not args.basedir:
        args.basedir = os.path.dirname(args.pipeline.name)

    if args.input is not None and not args.languages:
        parser.error('When --input is specified, each colum\'s LANG has to be specified as well.')

    pipeline = json.load(args.pipeline)

    # load all filter definitions (we need to, to get their name)
    FILTERS = {
        definition['name']: definition
        for definition in list_filters(os.path.join(args.filters, '*.json'))
    }

    # Assert we have all filters we need
    assert set(step['filter'] for step in pipeline['filters']) - set(FILTERS.keys()) == set()

    # List of child processes used for extracting & filtering dataset
    children: List[Popen] = []

    # List of threads that watch each child process, one for each child
    babysitters: List[Thread] = []

    def babysit(child: Popen, name: str):
        n = len(children)
        thread = Thread(target=babysit_child, args=[n, child, name, print_queue, ctrl_queue])
        thread.start()
        babysitters.append(thread)
        children.append(child)

    # Queue filled by the babysitters with the stderr of the children, consumed
    # by `print_lines()` to prevent racing on stderr.
    print_queue = SimpleQueue() # type: SimpleQueue[Optional[bytes]]

    # Queue filled by the babysitters with the return code of each of the
    # children. Used by the main thread to catch errors in the pipeline.
    ctrl_queue = SimpleQueue() # type: SimpleQueue[tuple[int, int]]

    if args.input:
        basepath = 'stdin'
    else:
        basepath = os.path.commonprefix(pipeline['files']).rstrip('.')

    # If we're not reading from stdin, read from files and paste them together
    if not args.input:
        # Matches datasets.py:list_datasets(path)
        languages = [
            filename.rsplit('.', 2)[1]
            for filename in pipeline['files']
        ]

        # Open `gzunip` for each language file
        for filename in pipeline['files']:
            child = Popen(
                ['gzip', '-cd', filename],
                stdout=PIPE,
                stderr=PIPE,
                cwd=args.basedir)

            babysit(child, f'gunzip {filename}')

        # .. and a `paste` to combine them into columns
        child = Popen(
            ['paste'] + [f'/dev/fd/{none_throws(child.stdout).fileno()}' for child in children],
            stdout=PIPE,
            stderr=PIPE,
            pass_fds=[none_throws(child.stdout).fileno() for child in children])

        babysit(child, 'paste')

        # Now that `paste` has inherited all the children, close our connection to them
        for child in children[:-1]:
            none_throws(child.stdout).close()

    else:
        languages = args.languages

    # First start the print thread so that we get immediate feedback from the
    # children even if all of them haven't started yet.
    print_thread = Thread(target=print_lines, args=[print_queue, sys.stderr.buffer])
    print_thread.start()

    # Start child processes, each reading the output from the previous sibling
    for i, step in enumerate(pipeline['filters']):
        filter_definition = FILTERS[step['filter']]
        
        if filter_definition['type'] == 'bilingual':
            command = filter_definition['command']
        elif filter_definition['type'] == 'monolingual':
            column = languages.index(step['language'])
            command = f'{COL_PY} {column} {filter_definition["command"]}'
        else:
            raise NotImplementedError()

        # List of k=v shell variable definitions
        filter_params = [
            '{}={}'.format(name, quote(encode_env(props['type'], step['parameters'][name])))
            for name, props in filter_definition['parameters'].items()    
        ]

        # Command, prefixed by variable definitions so they get expanded
        # correctly in the command bit.
        command_str = '; '.join(filter_params + [command])

        is_last_step = i + 1 == len(pipeline['filters'])

        child = Popen(command_str,
            stdin=args.input if len(children) == 0 else children[-1].stdout,
            stdout=args.output if is_last_step and not args.tee else PIPE,
            stderr=PIPE,
            cwd=filter_definition['basedir'],
            shell=True)

        # Close our reference to the child, now taken over by the next child
        if len(children) > 0:
            none_throws(children[-1].stdout).close()

        print_queue.put(f'[run.py] step {i}: Executing {command_str}\n'.encode())

        babysit(child, f'step {i}') # also does children.append(child)

        # If we are tee-ing for debug, shunt the output to a separate file
        # TODO: uncompressed at the moment. Might be trouble.
        if args.tee:
            tee = Popen(['tee', f'{basepath}.step-{i}.tsv'],
                stdin=child.stdout,
                stdout=args.output if is_last_step else PIPE,
                stderr=PIPE)

            none_throws(children[-1].stdout).close()

            babysit(tee, f'tee {i}')

    # Wait for the children to exit, and depending on their retval exit early
    running_children = len(children)

    try:
        while running_children > 0:
            child_i, retval = ctrl_queue.get()
            running_children -= 1

            # TODO: When Child N exits with exit code 0, kill all N-1 children
            # as well and ignore their exit code. This happens with e.g.
            # `head -n 10`.

            # Early exit when a process errored out
            if retval not in (0, -signal.SIGPIPE):
                break
    except KeyboardInterrupt:
        print('[run.py] KeyboardInterrupt', file=sys.stderr)
        pass

    # Wait for all the processes to prevent zombies
    for child in children:
        if child.returncode is None:
            child.wait()

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
