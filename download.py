#!/usr/bin/env python3
"""Various mtdata dataset downloading utilities"""
import os
from typing import NamedTuple, Optional, Iterable, Dict, List
from enum import Enum
from concurrent.futures import ProcessPoolExecutor, Future, wait
from subprocess import check_call, CalledProcessError
from itertools import zip_longest
from sys import stderr
from collections import defaultdict
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
from mtdata.entry import lang_pair
from mtdata.index import Index, get_entries
from mtdata.iso.bcp47 import bcp47, BCP47Tag


#datasets = {str(entry.did): entry for entry in get_entries()}


DOWNLOAD_PATH = 'data'


class EntryRef(BaseModel):
    id: str


class Entry(EntryRef):
    group: str
    name: str
    version: str
    langs: List[str]    


class DownloadState(Enum):
    PENDING = 'pending'
    CANCELLED = 'downloaded'
    DOWNLOADING = 'downloading'
    DOWNLOADED = 'downloaded'
    FAILED = 'failed'


class EntryDownload(NamedTuple):
    entry: Entry
    future: Future


class EntryDownloadView(BaseModel):
    entry: Entry
    state: DownloadState


app = FastAPI()

downloads: Dict[str, EntryDownload] = {}

downloader = ProcessPoolExecutor(2)


def cast_entry(entry) -> Entry:
    return Entry(
        id = str(entry.did),
        group = entry.did.group,
        name = entry.did.name,
        version = entry.did.version,
        langs = [lang.lang for lang in entry.did.langs]
    )


def cast_download_state(future:Future) -> DownloadState:
    if future.cancelled():
        return DownloadState.CANCELLED
    elif future.running():
        return DownloadState.DOWNLOADING
    elif future.done() and future.exception():
        return DownloadState.FAILED
    elif future.done():
        return DownloadState.DOWNLOADED
    else:
        return DownloadState.PENDING


@app.get("/languages/")
@app.get("/languages/{lang1}")
def list_languages(lang1:str = None) -> Iterable[str]:
   langs: set[str] = set()
   filter_lang = bcp47(lang1) if lang1 is not None else None
   for entry in Index.get_instance().get_entries():
       if filter_lang is not None and filter_lang not in entry.did.langs:
           continue
       langs.update(*entry.did.langs)
   return sorted(lang for lang in langs if lang is not None)


@app.get("/by-language/{langs}")
def list_datasets(langs:str) -> Iterable[Entry]:
    return dedupe_datasests(
        cast_entry(entry) for entry in get_entries(lang_pair(langs))
    )


@app.get('/downloads/')
def list_downloads() -> Iterable[EntryDownloadView]:
    return (
        EntryDownloadView(
            entry = download.entry,
            state = cast_download_state(download.future)
        )
        for download in downloads.values()
    )


@app.post('/downloads/')
def add_downloads(datasets: List[EntryRef]) -> Iterable[EntryDownloadView]:
    """Batch download requests!"""
    needles = set(dataset.id for dataset in datasets if dataset.id not in downloads)

    entries = [
        cast_entry(entry)
        for entry in Index.get_instance().get_entries()
        if str(entry.did) in needles
    ]

    for entry in entries:
        downloads[entry.id] = EntryDownload(
            entry=entry,
            future=downloader.submit(get_dataset, entry, DOWNLOAD_PATH)
        )

    return list_downloads()


@app.delete('/downloads/{dataset_id}')
def cancel_download(dataset_id:str) -> EntryDownloadView:
    """Cancel a download. Removes it from the queue, does not kill the process
    if download is already happening.
    """
    if dataset_id not in downloads:
        raise HTTPException(status_code=404, detail='Download not found')

    download = downloads[dataset_id]
    download.future.cancel()

    return EntryDownloadView(
        entry = download.entry,
        state = cast_download_state(download.future)
    )


def dedupe_datasests(datasets: Iterable[Entry]) -> Iterable[Entry]:
    """Mtdata contains a multitude a datasets that have many different versions
    (eg europarl). In the vast majority of the cases we ONLY EVER want the
    latest version
    """
    datadict: Dict[str, List[Entry]] = defaultdict(list)
    for entry in datasets:
        datadict[entry.name].append(entry)
    # Sort by version and return one per name
    return [
        sorted(entrylist, key=lambda t: t.version, reverse=True)[0]
        for entrylist in datadict.values()
    ]


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
    check_call(["mtdata", "get", "-l", "-".join(entry.langs), call_type, entry.id, "--compress",  "-o", path])
