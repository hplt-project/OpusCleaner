import os
import gzip
from typing import Optional, Iterable
from contextlib import ExitStack
from itertools import chain
from pydantic import BaseModel, parse_obj_as
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from enum import Enum
import json
import subprocess
import hashlib
from tempfile import TemporaryFile
from shutil import copyfileobj

from datasets import list_datasets
from sample import sample


DATA_PATH = 'data/train-parts'


FILTERS = {
    "remove-empty-lines": {
        "command": r"grep -vE '^\s*\t|\t\s*$'",
        "parameters": {}
    },
    "clean-parallel": {
        "command": "filters/clean_parallel.py -l1 $LANG1 -l2 $LANG2",
        "parameters": {
            "LANG1": {},
            "LANG2": {}
        }
    },
    "fix-elitr-eca": {
        "command": "filters/fix-elitr-eca.py",
        "parameters": {}
    },
}


class File(BaseModel):
    path: str
    size: int


class Dataset(BaseModel):
    name: str
    columns: dict[str,File]


class FilterStep(BaseModel):
    filter: str
    parameters: dict[str,str]


def sample_path(name:str, langs: Iterable[str]):
    languages = '.'.join(sorted(langs))
    return os.path.join(DATA_PATH, f'.sample.{name}.{languages}.gz')


def compute_sample(name:str, columns:list[tuple[str,os.DirEntry]]):
    langs = [lang for lang, _ in columns]
    with ExitStack() as ctx, gzip.open(sample_path(name, langs), 'wb') as fout:
        files = [ctx.enter_context(gzip.open(file.path, 'rb')) for _, file in columns]

        pairs = zip(*files)
        
        head, middle, tail = sample(10, pairs)

        for pair in chain(head, middle, tail):
            fout.write(b'\t'.join(line.rstrip(b'\n') for line in pair) + b'\n')


def get_sample(name:str, filters:list[FilterStep]) -> list[dict[str,str]]:
    columns: list[tuple[str,os.DirEntry]] = sorted(list_datasets(DATA_PATH).get(name).items(), key=lambda pair: pair[0])
    langs = [lang for lang, _ in columns]

    # If we don't have a sample stored, generate one. Doing it in bytes because
    # it might save us parsing utf-8 (also assumptions! It it utf-8?)
    if not os.path.exists(sample_path(name, langs)):
        compute_sample(name, columns)

    sample_file = sample_path(name, langs)

    filter_hash = ''

    for i, filter_step in enumerate(filters):
        filter_json = json.dumps(filter_step.dict(), sort_keys=True)
        filter_hash = hashlib.sha256((filter_hash + filter_json).encode()).hexdigest()
        if not os.path.exists(sample_path(name, langs) + filter_hash):
            with open(sample_file, 'rb') as fin, TemporaryFile('w+b') as fout:
                # Decompress input
                p_gunzip = subprocess.Popen(['pigz', '-cd'], stdin=fin, stdout=subprocess.PIPE)

                # Compress output
                p_gzip = subprocess.Popen(['pigz', '-9c'], stdin=subprocess.PIPE, stdout=fout)

                filter_env = os.environ.copy()
                for name, props in FILTERS[filter_step.filter].get('parameters', dict()).items():
                    filter_env[name] = filter_step.parameters[name]

                p_filter = subprocess.Popen([FILTERS[filter_step.filter]['command']],
                    env=filter_env, stdin=p_gunzip.stdout, stdout=p_gzip.stdin, shell=True)

                # Disconnect from the pipes only used by the spawned processes
                if p_gunzip.stdout:
                    p_gunzip.stdout.close()

                if p_gzip.stdin:
                    p_gzip.stdin.close()

                # Check exit codes, testing most obvious problems first.
                if p_filter.wait() != 0:
                    raise Exception(f"Step {i}: {filter_step.filter} failed")

                if p_gunzip.wait() != 0:
                    raise Exception(f"Decompression of input {sample_file} for step {i} failed. Previous step might have caused an error?")

                if p_gzip.wait() != 0:
                    raise Exception(f"Compression & writing output to temp file failed. Did the filter in {i} crash?")

                # Now we know reading was a success, move data to a more permanent location.
                with open(sample_path(name, langs) + filter_hash, 'wb') as fdest:
                    fout.seek(0)
                    copyfileobj(fout, fdest)

        sample_file = sample_path(name, langs) + filter_hash


    # Read the sample data as a dict[lang:str: line:str]
    with gzip.open(sample_file, 'rt') as fh:
        return [dict(zip(langs, line.rstrip('\n').split('\t'))) for line in fh]


app = FastAPI()

app.mount('/static', StaticFiles(directory='static'), name='static')

@app.get('/datasets/')
def api_list_datasets() -> list[Dataset]:
    return [
        Dataset(name=name, columns={
            lang: File(path=file.name, size=file.stat().st_size)
            for lang, file in columns.items()
        })
        for name, columns in list_datasets(DATA_PATH).items()
    ]


@app.get('/datasets/{name}/sample')
def api_get_dataset(name:str) -> list[dict[str,str]]:
    return get_sample(name, [])


@app.post('/datasets/{name}/sample')
def api_get_filtered_dataset(name:str, filters:list[FilterStep]) -> list[dict[str,str]]:
    return get_sample(name, filters)


@app.get('/filters/')
def api_get_filters():
    return FILTERS


@app.get('/')
def redirect_to_interface():
    return RedirectResponse('/static/index.html')


if __name__ == '__main__':
    from pprint import pprint

    filters = [
        {
            'filter': 'remove-empty-lines',
            'parameters': {}
        },
        {
            'filter': 'fix-elitr-eca',
            'parameters': {}
        },
        {
            'filter': 'clean-parallel',
            'parameters': {
                'LANG1': 'eng',
                'LANG2': 'fra'
            }
        }
        ]
    pprint(get_sample('OPUS-elitr_eca-v1-eng-fra', parse_obj_as(list[FilterStep], filters)))

