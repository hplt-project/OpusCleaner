#!/usr/bin/env python3
"""Various mtdata dataset downloading utilities"""
import os
from typing import Optional, Iterable, Dict, List
from concurrent.futures import ProcessPoolExecutor
from subprocess import check_call, CalledProcessError
from itertools import zip_longest
from sys import stderr
from collections import defaultdict
from pydantic import BaseModel
from fastapi import FastAPI
from mtdata.entry import lang_pair
from mtdata.index import Index, get_entries
from mtdata.iso.bcp47 import bcp47, BCP47Tag


datasets = {str(entry.did): entry for entry in get_entries()}


app = FastAPI()


class Entry(BaseModel):
    id: str
    group: str
    name: str
    version: str
    langs: List[str]


@app.get("/datasets/by-language")
@app.get("/datasets/by-language/{lang1}")
def list_languages(lang1:str = None) -> Iterable[str]:
    langs: set[str] = set()
    filter_lang = bcp47(lang1) if lang1 is not None else None
    for entry in Index.get_instance().get_entries():
        if filter_lang is not None and filter_lang not in entry.did.langs:
            continue
        langs.update(*entry.did.langs)
    return sorted(lang for lang in langs if lang is not None)


@app.get("/datasets/by-language/{langs}")
def list_datasets(langs:str) -> Iterable[Entry]:
    return (
        Entry(
            id = str(entry.did),
            group = entry.did.group,
            name = entry.did.name,
            version = entry.did.version,
            langs = [lang.lang for lang in entry.did.langs]
        ) for entry in get_entries(lang_pair(langs))
    )

def dedupe_datasests(datasets: Iterable[Entry]) -> Iterable[Entry]:
    """Mtdata contains a multitude a datasets that have many different versions
    (eg europarl). In the vast majority of the cases we ONLY EVER want the latest version"""
    datadict: Dict[str, List[Entry]] = defaultdict(list)
    for entry in datasets:
        datadict[entry.name].append(entry)
    # Sort by version and return one per name
    return ([sorted(entrylist, key=lambda t: t.version, reverse=True)[0] for entrylist in datadict.values()])

def get_dataset(entry: Entry, path: str) -> None:
    """Gets datasets, using a subprocess call to mtdata. Might be less brittle to internal
    mtdata interface changes"""
    call_type: str # We have train/test/dev
    if "dev" in entry.name:
        call_type = "-dv"
    elif "test" in entry.name:
        call_type = "-ts"
    else:
        call_type = "-tr"
    # Download the dataset
    try:
        check_call(["mtdata", "get", "-l", "-".join(entry.langs), call_type, entry.id, "--compress",  "-o", path])
    except CalledProcessError as err:
        print("Error downloading dataset:", entry.id, file=stderr)
        print(err.cmd, file=stderr)
        print(err.stderr, file=stderr)

def get_datasets(datasets: Iterable[Entry], path: str, num_threads: int=2) -> None:
    """Gets multiple datasets with up to num_theads parallel downloads"""
    executor = ProcessPoolExecutor(max_workers=num_threads)
    executor.map(lambda mytupple: get_dataset(mytupple[0], mytupple[1]), zip_longest(datasets, [], path))


@app.get("/datasets/{did}")
def read_dataset(did: str):
    return datasets[did].did


@app.get("/datasets/{did}/sample")
def read_dataset(did: str):
    return datasets[did].did

def test() -> None:
    """Tests downloading all eng-bul datasests with a threadpool of subprocess calls"""
    if not os.path.exists('data'):
        os.makedirs('data')
    datasets = dedupe_datasests(list_datasets("eng-bul"))
    get_datasets(datasets, 'data', 4)
