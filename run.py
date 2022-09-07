#!/usr/bin/env python3
import sys
import os
import argparse
import json
import glob
import asyncio
import subprocess

COL_PY = os.path.join(os.path.dirname(__file__), 'col.py')

def encode_env(type_name, value):
    if type_name == 'bool':
        return '1' if value else '0'
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


async def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('--filters', '-f', type=str, default='./filters')
    parser.add_argument('--input', '-i', type=argparse.FileType('rb'), default=sys.stdin.buffer)
    parser.add_argument('--output', '-o', type=argparse.FileType('wb'), default=sys.stdout.buffer)
    parser.add_argument('steps', metavar='FILTERSTEPS', type=argparse.FileType('r'))
    parser.add_argument('languages', metavar='LANG', type=str, nargs=2)

    args = parser.parse_args(argv)

    steps = json.load(args.steps)

    FILTERS = {
        definition['name']: definition
        for definition in list_filters(os.path.join(args.filters, '*.json'))
    }

    # Assert we have all filters we need
    assert set(step['filter'] for step in steps) - set(FILTERS.keys()) == set()

    processes = []

    for i, step in enumerate(steps):
        filter_definition = FILTERS[step['filter']]
        
        filter_env = os.environ.copy()
        for name, props in filter_definition['parameters'].items():
            filter_env[name] = encode_env(filter_definition['type'], step['parameters'][name])

        if filter_definition['type'] == 'bilingual':
            command = filter_definition['command']
        elif filter_definition['type'] == 'monolingual':
            column = args.languages.index(step['language'])
            command = f'{COL_PY} {column} {filter_definition["command"]}'
        else:
            raise NotImplementedError()

        is_first_step = i == 0
        is_last_step = i + 1 == len(steps)
        
        process = subprocess.Popen(command,
            stdin=args.input if is_first_step else processes[-1].stdout,
            stdout=args.output if is_last_step else subprocess.PIPE,
            env=filter_env,
            cwd=filter_definition['basedir'],
            shell=True)

        processes.append(process)

    for i, process in enumerate(processes):
        process.wait()

    for i, process in enumerate(processes):
        if process.returncode != 0:
            print(f"Step {i} failed with return code {preocess.returncode}", file=sys.stderr)

    if any(process.returncode != 0 for process in processes):
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(main(sys.argv[1:]))
