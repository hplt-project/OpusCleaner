#!/usr/bin/env python3
"""Lists datasets given a directory. It works by scanning the directory and looking for gz files."""
import os
import glob
from itertools import groupby
from pathlib import Path
from typing import Iterable, Dict


def _glob(*args, **kwargs) -> Iterable[Path]:
    for entry in glob.glob(*args, **kwargs):
        yield Path(entry)


def list_datasets(path) -> Dict[str,Dict[str,Path]]:
    """Lists datasets given a directory. Scans the directories and returns a dictionary of the
    datasets encoutered. Dictionary looks like {dataset_name : { lang: path}}"""
    root = Path(path.split('*')[0])

    files = [
        entry
        for entry in _glob(path, recursive=True)
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
        name: {
            entry.name.rsplit('.', 2)[1]: entry
            for entry in files
        }
        for name, files in datasets
        if len(files) > 1
    }


def main():
    import sys
    import pprint
    pprint.pprint(list_datasets(sys.argv[1]))


if __name__ == '__main__':
    main()
