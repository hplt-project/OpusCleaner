#!/usr/bin/env python3
"""Various mtdata dataset downloading utilities"""
import os
import sys
import asyncio
import json
from glob import iglob
from itertools import chain
from typing import Iterable, Dict, List, Optional, Set, Union, Tuple
from enum import Enum
from queue import SimpleQueue
from subprocess import Popen
from threading import Thread
from collections import defaultdict
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from pprint import pprint
from operator import itemgetter
from warnings import warn

from pydantic import BaseModel
from mtdata.entry import lang_pair
from mtdata.iso.bcp47 import bcp47, BCP47Tag
from fastapi import FastAPI, HTTPException

from config import DATA_PATH, DOWNLOAD_PATH


class EntryRef(BaseModel):
    id: int


class Entry(EntryRef):
    corpus: str
    version: str
    langs: List[BCP47Tag]


class LocalEntry(Entry):
    paths: Set[str]
    size: Optional[int] # Size on disk


class RemoteEntry(Entry):
    url: str
    size: int


class DownloadState(Enum):
    PENDING = 'pending'
    CANCELLED = 'cancelled'
    DOWNLOADING = 'downloading'
    DOWNLOADED = 'downloaded'
    FAILED = 'failed'


def get_dataset(entry: Entry, path: str) -> Popen:
    raise NotImplementedError()


class EntryDownload:
    entry: Entry

    def __init__(self, entry:Entry):
        self.entry = entry
        self._child = None
    
    def start(self):
        self._child = get_dataset(self.entry, DOWNLOAD_PATH)

    def run(self):
        self.start()
        assert self._child is not None
        self._child.wait()

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
            entry.run()


class EntryDownloadView(BaseModel):
    entry: Entry
    state: DownloadState


class OpusAPI:
    def __init__(self, endpoint):
        self.endpoint = endpoint

    def languages(self, lang1: Optional[str] = None) -> Dict[str,BCP47Tag]:
        query = {'languages': 'True'}

        if lang1 is not None:
            query['source'] = lang1

        languages = {}
        with urlopen(f'{self.endpoint}?{urlencode(query)}') as fh:
            for lang in json.load(fh).get('languages', []):
                try:
                    languages[lang] = bcp47(lang)
                except Exception as e:
                    warn(f'Could not parse {lang} as BCP47: {e!s}')
        return languages

    def find_datasets(self, lang1, lang2) -> List[Entry]:
        query = {
            'source': lang1,
            'target': lang2,
            'preprocessing': 'smt' # TODO: also add xml separately?
        }
        with urlopen(f'{self.endpoint}?{urlencode(query)}') as fh:
            return [cast_entry(entry) for entry in json.load(fh).get('corpora', [])]


app = FastAPI()

api = OpusAPI('https://opus.nlpl.eu/opusapi/')

downloads: Dict[str, EntryDownload] = {}

downloader = Downloader(2)


def cast_entry(entry, **kwargs) -> Entry:
    args = dict(
        id = int(entry['id']),
        corpus = str(entry['corpus']),
        version = str(entry['version']),
        langs = [bcp47(entry['source']), bcp47(entry['target'])],
        **kwargs)

    paths = set(
        filename
        for data_root in [os.path.dirname(DATA_PATH), DOWNLOAD_PATH]
        for lang in args['langs']
        for filename in iglob(os.path.join(data_root, f'{args["corpus"]!s}.{lang.lang}.gz'), recursive=True)
    )

    if paths:
        return LocalEntry(
            **args,
            paths=paths,
            size=int(entry['size']))
    else:
        return RemoteEntry(
            **args,
            url=str(entry['url']))


@app.get("/languages/")
@app.get("/languages/{lang1}")
def list_languages(lang1:Optional[str] = None) -> List[Dict[str,str]]:
    return sorted([
        {
            'id': key,
            'tag': lang.tag.replace('_', '-') # mtdata uses the non-standard `_` because `-` is used for pairs already
        }
        for key, lang in api.languages(lang1).items()
    ], key=itemgetter('tag'))


@app.get("/by-language/{langs}")
def list_datasets(langs:str) -> Iterable[Entry]:
    return api.find_datasets(*lang_pair(langs))


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
    raise NotImplementedError('OpusAPI has no id -> dataset endpoint')
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
