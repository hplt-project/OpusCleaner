#!/usr/bin/env python3
"""Lists datasets given a directory. It works by scanning the directory and looking for gz files."""
import asyncio
import os
import pprint
import sys
from glob import glob
from itertools import groupby
from pathlib import Path
from shutil import copyfileobj
from tempfile import TemporaryFile
from typing import Dict, List, Tuple, Iterable

from opuscleaner.config import DATA_PATH, SAMPLE_PY, SAMPLE_SIZE


def list_datasets(path:str) -> Dict[str,List[Tuple[str,Path]]]:
    """Lists datasets given a directory. Scans the directories and returns a dictionary of the
    datasets encoutered. Dictionary looks like {dataset_name : { lang: path}}"""
    root = Path(path.split('*')[0])

    entries = (Path(entry) for entry in glob(path, recursive=True))

    files = [
        entry
        for entry in entries
        if entry.is_file()
        and entry.name.endswith('.gz')
        and not entry.name.startswith('.')
    ]

    datasets = [
        (name, list(files))
        for name, files in groupby(
            sorted(files, key=lambda entry: str(entry)),
            key=lambda entry: str(entry.relative_to(root)).rsplit('.', 2)[0])
    ]

    return {
        name: [
            (entry.name.rsplit('.', 2)[1], entry)
            for entry in files
        ]
        for name, files in datasets
    }


def dataset_path(name:str, template:str) -> str:
    # TODO: fix this hack to get the file path from the name this is silly we
    # should just use get_dataset(name).path or something
    root = DATA_PATH.split('*')[0]

    # If the dataset name is a subdirectory, do some hacky shit to get to a
    # .sample.gz file in said subdirectory.
    parts = name.rsplit('/', maxsplit=2)
    if len(parts) == 2:
        root = os.path.join(root, parts[0])
        filename = parts[1]
    else:
        filename = parts[0]

    return os.path.join(root, template.format(filename))


def filter_configuration_path(name:str) -> str:
    return dataset_path(name, '{}.filters.json')


def sample_path(name:str, langs:Iterable[str]) -> str:
    languages = '.'.join(sorted(langs))
    return dataset_path(name, f'.sample.{{}}.{languages}')


def main_list_commands(args):
    print("Error: No command specified.\n\n"
          "Available commands:\n"
          "  list       list datasets\n"
          "  sample     sample all datasets\n"
          "", file=sys.stderr)
    sys.exit(1)


async def sample_all_datasets(args):
    tasks = []

    for name, columns in list_datasets(DATA_PATH).items():
        langs = [lang for lang, _ in columns]
        if not os.path.exists(sample_path(name, langs)) or args.force:
            print(f"Sampling {name}...", file=sys.stderr)
            tasks.append([name, columns])

    for task, result in zip(tasks, await asyncio.gather(*[compute_sample(*task) for task in tasks], return_exceptions=True)):
        if isinstance(result, Exception):
            print(f"Could not compute sample for {task[0]}: {result!s}", file=sys.stderr)


async def compute_sample(name:str, columns:List[Tuple[str,Path]]) -> None:
    langs = [lang for lang, _ in columns]
    with TemporaryFile() as tempfile:
        proc = await asyncio.subprocess.create_subprocess_exec(
            *SAMPLE_PY,
            '-n', str(SAMPLE_SIZE),
            *[str(file.resolve()) for _, file in columns],
            stdout=tempfile,
            stderr=asyncio.subprocess.PIPE)

        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise Exception(f'sample.py failed with exit code {proc.returncode}: {stderr.decode()}')

        tempfile.seek(0)

        with open(sample_path(name, langs), 'wb') as fdest:
            copyfileobj(tempfile, fdest)


def main_list(args):
	pprint.pprint(list_datasets(args.path))


def main_sample(args):
    asyncio.run(sample_all_datasets(args))


def main(argv=sys.argv):
    import argparse

    parser = argparse.ArgumentParser(description='Fill up those seats on your empty train.')
    parser.set_defaults(func=main_list_commands)
    subparsers = parser.add_subparsers()

    parser_serve = subparsers.add_parser('list')
    parser_serve.add_argument('path', nargs="?", type=str, default=DATA_PATH)
    parser_serve.set_defaults(func=main_list)

    parser_sample = subparsers.add_parser('sample')
    parser_sample.add_argument("--force", "-f", action="store_true")
    parser_sample.set_defaults(func=main_sample)

    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
