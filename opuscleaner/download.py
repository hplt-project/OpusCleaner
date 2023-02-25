#!/usr/bin/env python3
"""Various mtdata dataset downloading utilities"""
import os
import sys
import asyncio
import json
import gzip
from glob import iglob
from itertools import chain
from typing import Iterable, Dict, List, Optional, Set, Union, Tuple, cast
from enum import Enum
from queue import SimpleQueue
from subprocess import Popen, PIPE
from threading import Thread
from collections import defaultdict
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from pprint import pprint
from operator import itemgetter
from warnings import warn
from tempfile import TemporaryDirectory, TemporaryFile
from shutil import copyfileobj
from multiprocessing import Process
from zipfile import ZipFile

from pydantic import BaseModel
from fastapi import FastAPI, HTTPException

from .config import DATA_PATH, DOWNLOAD_PATH


class EntryRef(BaseModel):
    id: int


class Entry(EntryRef):
    corpus: str
    version: str
    langs: Tuple[str,str]
    pairs: Optional[int] # Number of sentence pairs
    size: Optional[int] # Size on disk in bytes (rounded to lowest 1024)

    @property
    def basename(self) -> str:
        return f'{self.corpus}-{self.version}.{"-".join(self.langs)}'


class LocalEntry(Entry):
    paths: Set[str]


class RemoteEntry(Entry):
    url: str


class DownloadState(Enum):
    PENDING = 'pending'
    CANCELLED = 'cancelled'
    DOWNLOADING = 'downloading'
    DOWNLOADED = 'downloaded'
    FAILED = 'failed'


def get_dataset(entry: RemoteEntry, path: str):
    # List of extensions of the expected files, e.g. `.en-mt.mt` and `.en-mt.en`.
    suffixes = [f'.{"-".join(entry.langs)}.{lang}' for lang in entry.langs]

    with TemporaryFile() as temp_archive:
        # Download zip file to temporary file
        with urlopen(entry.url) as fh:
            copyfileobj(fh, temp_archive)

        # Then selectively extract that zipfile to a temporary directory
        with TemporaryDirectory(dir=path) as temp_extracted:
            files = []

            with ZipFile(temp_archive) as archive:
                for info in archive.filelist:
                    if info.is_dir() or not any(info.filename.endswith(suffix) for suffix in suffixes):
                        continue

                    # `info.filename` is something like "beepboop.en-nl.en", `lang` will be "en".
                    _, lang = info.filename.rsplit('.', maxsplit=1)

                    filename = f'{entry.basename}.{lang}.gz'
                    temp_dest = os.path.join(temp_extracted, filename)
                    data_dest = os.path.join(path, filename)

                    # Extract the file from the zip archive into the temporary directory, compress
                    # it while we're at it.
                    with archive.open(info) as fin, gzip.open(temp_dest, 'wb') as fout:
                        copyfileobj(fin, fout)

                    # Keep a list of extracted files, and where they eventually need to go to
                    files.append((temp_dest, data_dest))

            # Once we know all files extracted as expected, move them to their permanent place.
            for temp_path, dest_path in files:
                os.rename(temp_path, dest_path)


class EntryDownload:
    entry: RemoteEntry
    _child: Optional[Process]

    def __init__(self, entry:RemoteEntry):
        self.entry = entry
        self._child = None
    
    def start(self):
        self._child = Process(target=get_dataset, args=(self.entry, DOWNLOAD_PATH))
        self._child.start()

    def run(self):
        self.start()
        assert self._child is not None
        self._child.join()

    def cancel(self):
        if self._child and self._child.exitcode is None:
            self._child.kill()

    @property
    def state(self):
        if not self._child:
            return DownloadState.PENDING
        elif self._child.exitcode is None:
            return DownloadState.DOWNLOADING
        elif self._child.exitcode == 0:
            return DownloadState.DOWNLOADED
        elif self._child.exitcode > 0:
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

    def download(self, entry:RemoteEntry) -> EntryDownload:
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
    endpoint: str

    _datasets: Dict[int,Entry] = {}

    def __init__(self, endpoint):
        self.endpoint = endpoint
        self._datasets = {}

    def languages(self, lang1: Optional[str] = None) -> List[str]:
        query = {'languages': 'True'}

        if lang1 is not None:
            query['source'] = lang1

        with urlopen(f'{self.endpoint}?{urlencode(query)}') as fh:
            return json.load(fh).get('languages', [])

    def get_dataset(self, id:int) -> Entry:
        return self._datasets[id]

    def find_datasets(self, lang1:str, lang2:str) -> List[Entry]:
        query = {
            'source': lang1,
            'target': lang2,
            'preprocessing': 'moses'
        }
        
        with urlopen(f'{self.endpoint}?{urlencode(query)}') as fh:
            datasets = [cast_entry(entry) for entry in json.load(fh).get('corpora', [])]

        # FIXME dirty hack to keep a local copy to be able to do id based lookup
        # Related: https://github.com/Helsinki-NLP/OPUS-API/issues/3
        for dataset in datasets:
            self._datasets[dataset.id] = dataset

        return datasets


app = FastAPI()

api = OpusAPI('https://opus.nlpl.eu/opusapi/')

downloads: Dict[int,EntryDownload] = {}

downloader = Downloader(2)

datasets_by_id: Dict[int, Entry] = {}

def cast_entry(data) -> Entry:
    entry = Entry(
        id=int(data['id']),
        corpus=str(data['corpus']),
        version=str(data['version']),
        pairs=int(data['alignment_pairs']) if data.get('alignment_pairs') != '' else None,
        size=int(data['size']) * 1024, # FIXME file size but do we care?
        langs=(data['source'], data['target']), # FIXME these are messy OPUS-API lang codes :(
    )

    paths = set(
        filename
        for data_root in [os.path.dirname(DATA_PATH), DOWNLOAD_PATH]
        for lang in cast(Tuple[str,str], entry.langs)
        for filename in iglob(os.path.join(data_root, f'{entry.basename}.{lang}.gz'), recursive=True)
    )

    # Print search paths
    # print('\n'.join(
    #     filename
    #     for data_root in [os.path.dirname(DATA_PATH), DOWNLOAD_PATH]
    #     for lang in cast(Tuple[str,str], entry.langs)
    #     for filename in [os.path.join(data_root, f'{entry.basename}.{lang}.gz')]
    # ))

    if paths:
        return LocalEntry(
            **entry.__dict__,
            paths=paths)
    else:
        return RemoteEntry(
            **entry.__dict__,
            url=str(data['url']))


@app.get("/languages/")
@app.get("/languages/{lang1}")
def list_languages(lang1:Optional[str] = None) -> List[str]:
    return sorted(api.languages(lang1))


@app.get("/by-language/{langs}")
def list_datasets(langs:str) -> Iterable[Entry]:
    return api.find_datasets(*langs.split('-'))


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
        api.get_dataset(id) for id in needles
    ]

    for entry in entries:
        assert isinstance(entry, RemoteEntry)
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
