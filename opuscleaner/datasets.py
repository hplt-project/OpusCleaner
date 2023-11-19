#!/usr/bin/env python3
"""Lists datasets given a directory. It works by scanning the directory and looking for gz files."""
from glob import glob
from itertools import groupby
from pathlib import Path as Path
from typing import Dict, List, Tuple

from opuscleaner.config import DATA_PATH


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


def main() -> None:
    import sys
    import pprint
    if len(sys.argv) == 1:
        pprint.pprint(list_datasets(DATA_PATH))
    else:
        pprint.pprint(list_datasets(sys.argv[1]))


if __name__ == '__main__':
    main()
