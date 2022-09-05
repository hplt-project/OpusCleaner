from typing import Optional, Iterable
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
            langs = entry.did.langs
        ) for entry in get_entries(lang_pair(langs))
    )


@app.get("/datasets/{did}")
def read_dataset(did: str):
    return datasets[did].did


@app.get("/datasets/{did}/sample")
def read_dataset(did: str):
    return datasets[did].did
