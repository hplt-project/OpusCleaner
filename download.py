#!/usr/bin/env python3
"""Various mtdata dataset downloading utilities"""
import os
import sys
import asyncio
from glob import iglob
from itertools import chain
from typing import Iterable, Dict, List, Optional, Set, Union, Tuple
from enum import Enum
from queue import SimpleQueue
from subprocess import Popen
from threading import Thread
from collections import defaultdict
from urllib.request import Request, urlopen
from pprint import pprint

import mtdata.entry
from mtdata.entry import lang_pair, DatasetId
from mtdata.index import Index, get_entries
from mtdata.iso.bcp47 import bcp47, BCP47Tag
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException

from config import DATA_PATH, DOWNLOAD_PATH


class EntryRef(BaseModel):
    id: str


class Entry(EntryRef):
    group: str
    name: str
    version: str
    langs: List[str]
    cite: Optional[str]


class LocalEntry(Entry):
    paths: Set[str]
    size: Optional[int] # Size on disk


class RemoteEntry(Entry):
    url: str
    size: Optional[int] # 'Content-Length' from a HTTP HEAD request


class DownloadState(Enum):
    PENDING = 'pending'
    CANCELLED = 'cancelled'
    DOWNLOADING = 'downloading'
    DOWNLOADED = 'downloaded'
    FAILED = 'failed'


def get_dataset(entry: Entry, path: str) -> Popen:
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
    return Popen(["mtdata", "get", "-l", "-".join(entry.langs), call_type, entry.id, "--compress",  "-o", path])


class EntryDownload:
    entry: Entry

    def __init__(self, entry:Entry):
        self.entry = entry
        self._child = None
    
    def start(self):
        self._child = get_dataset(self.entry, DOWNLOAD_PATH)

    def cancel(self):
        if self._child and self._child.returncode is None:
            self._child.kill()

    @property
    def state(self):
        if not self._child:
            return DownloadState.PENDING
        elif self._child.returncode is None:
            return DownloadState.DOWNLOADING
        elif self._child.returncode == 0:
            return DownloadState.DOWNLOADED
        elif self._child.returncode > 0:
            return DownloadState.FAILED
        else:
            return DownloadState.CANCELLED


class Downloader:
    def __init__(self, workers:int):
        self.queue = SimpleQueue()
        self.threads = []

        for _ in range(workers):
            thread = Thread(target=self.__class__.worker_thread, args=[self.queue], daemon=True)
            thread.start()
            self.threads.append(thread)

    def download(self, entry:Entry) -> EntryDownload:
        download = EntryDownload(entry=entry)
        self.queue.put(download)
        return download

    @staticmethod
    def worker_thread(queue):
        while True:
            entry = queue.get()
            if not entry:
                break
            entry.start()
            entry._child.wait()


class EntryDownloadView(BaseModel):
    entry: Entry
    state: DownloadState


app = FastAPI()

downloads: Dict[str, EntryDownload] = {}

downloader = Downloader(2)


def find_local_paths(entry: mtdata.entry.Entry) -> Set[str]:
    return set(
        filename
        for data_root in [os.path.dirname(DATA_PATH), DOWNLOAD_PATH]
        for lang in entry.did.langs
        for filename in iglob(os.path.join(data_root, f'{entry.did!s}.{lang.lang}.gz'), recursive=True)
    )


def cast_entry(entry, **kwargs) -> Entry:
    args = dict(
        id = str(entry.did),
        group = entry.did.group,
        name = entry.did.name,
        version = entry.did.version,
        langs = [lang.lang for lang in entry.did.langs],
        cite = entry.cite,
        **kwargs)

    paths = find_local_paths(entry)
    if paths:
        return LocalEntry(
            **args,
            paths=paths,
            size=sum(os.stat(path).st_size for path in paths))
    else:
        return RemoteEntry(
            **args,
            url=entry.url)


@app.get("/languages/")
@app.get("/languages/{lang1}")
def list_languages(lang1:Optional[str] = None) -> Iterable[str]:
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
            state = download.state
        )
        for download in downloads.values()
    )


@app.post('/downloads/')
def batch_add_downloads(datasets: List[EntryRef]) -> Iterable[EntryDownloadView]:
    """Batch download requests!"""
    needles = set(dataset.id
        for dataset in datasets
        if dataset.id not in downloads)

    entries = [
        cast_entry(entry)
        for entry in Index.get_instance().get_entries()
        if str(entry.did) in needles
    ]

    for entry in entries:
        downloads[entry.id] = downloader.download(entry)

    return list_downloads()


@app.delete('/downloads/{dataset_id}')
def cancel_download(dataset_id:str) -> EntryDownloadView:
    """Cancel a download. Removes it from the queue, does not kill the process
    if download is already happening.
    """
    if dataset_id not in downloads:
        raise HTTPException(status_code=404, detail='Download not found')

    download = downloads[dataset_id]
    download.cancel()

    return EntryDownloadView(
        entry = download.entry,
        state = download.state
    )


def http_request_head(url):
    request = Request(url, method='HEAD')
    with urlopen(request) as fh:
        return fh.headers


@app.get('/datasets/{dataset_id}')
async def get_dataset_details(dataset_id:str) -> RemoteEntry:
    key = DatasetId.parse(dataset_id)
    dataset = Index.get_instance().entries[key]
    headers = await asyncio.to_thread(http_request_head, dataset.url)
    
    # Some sites, like ELRC-share, don't return a proper response at all...
    if headers.get('content-type', '').startswith('text/html') or 'content-length' not in headers:
        size = None
    else:
        size = int(headers.get('content-length'))
    
    return cast_entry(dataset, size=size)


@app.get('/dataset-headers/{dataset_id}')
async def get_dataset_details(dataset_id:str):
    key = DatasetId.parse(dataset_id)
    dataset = Index.get_instance().entries[key]
    return {
        'request': {
            'url': dataset.url,
        },
        'headers': await asyncio.to_thread(http_request_head, dataset.url)
    }


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
