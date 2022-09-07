#!/usr/bin/env python3
import os
import gzip
import sys
import re
from typing import Optional, Iterable, TypeVar, Union, Literal, Any, AsyncIterator, cast, IO, List, Dict, Tuple
from contextlib import ExitStack
from itertools import chain
from pydantic import BaseModel, parse_obj_as, validator
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, StreamingResponse, HTMLResponse
from fastapi.encoders import jsonable_encoder
import anyio
from starlette.datastructures import URL
from starlette.exceptions import HTTPException
from starlette.responses import FileResponse, RedirectResponse, Response
from starlette.types import Scope
from enum import Enum
import asyncio
import json
import subprocess
import hashlib
from glob import glob
from tempfile import TemporaryFile
from shutil import copyfileobj
from pprint import pprint

import opusfilter.filters as opusfilters


from datasets import list_datasets, Path
from sample import sample


DATA_PATH = os.getenv('DATA_PATH', 'data/train-parts/*.*.gz')

FILTER_PATH = 'filters/*.json'

# col.py is used to apply a monolingual filter to a bilingual dataset. Needs
# to be absolute since filters can run from different cwds.
COL_PY = os.path.abspath('./col.py')

SAMPLE_PY = os.path.abspath('./sample.py')

# Size of each of the three sections (head, random sample of middle, tail) of
# the dataset sample that we operate on.
SAMPLE_SIZE = int(os.getenv('SAMPLE_SIZE', '100'))


class File(BaseModel):
    path: str
    size: int


class Dataset(BaseModel):
    name: str
    columns: Dict[str,File]


class FilterType(Enum):
    BILINGUAL = "bilingual"
    MONOLINGUAL = "monolingual"


class FilterParameterBase(BaseModel):
    type: str
    help: Optional[str]

    def export(self, value: Any) -> str:
        return str(value)


class FilterParameterFloat(FilterParameterBase):
    type: Literal["float"]
    min: Optional[float]
    max: Optional[float]
    default: Optional[float]

    def export(self, value: Any) -> float:
        return float(value)


class FilterParameterInt(FilterParameterBase):
    type: Literal["int"]
    min: Optional[int]
    max: Optional[int]
    default: Optional[int]

    def export(self, value: Any) -> int:
        return int(value)


class FilterParameterBool(FilterParameterBase):
    type: Literal["bool"]
    default: Optional[bool]

    def export(self, value: Any) -> bool:
        return bool(value)


class FilterParameterStr(FilterParameterBase):
    type: Literal["str"]
    default: Optional[str]
    allowed_values: Optional[List[str]]


FilterParameter = Union[
    FilterParameterFloat,
    FilterParameterInt,
    FilterParameterBool,
    FilterParameterStr
]


class Filter(BaseModel):
    type: FilterType
    name: str # comes from filename by default
    description: Optional[str]
    command: str
    basedir: Optional[str] # same as .json file by default
    parameters: Dict[str,FilterParameter]


class FilterStep(BaseModel):
    filter: str
    parameters: Dict[str,Any]
    language: Optional[str]

    @validator('filter')
    def check_filter(cls, filter):
        if filter not in FILTERS:
            raise ValueError(f'Unknown filter `{filter}`')
        return filter

    @validator('parameters')
    def check_parameters(cls, parameters, values, **kwargs):
        if 'filter' in values:
            required = set(FILTERS[values['filter']].parameters.keys())
            provided = set(parameters.keys())
            if len(required - provided) > 0:
                raise ValueError(f"Missing filter parameters: {' '.join(required - provided)}")
            if len(provided - required) > 0:
                raise ValueError(f"Provided parameters not supported by the filter: {' '.join(provided - required)}")
        return parameters

    @validator('language', always=True)
    def check_language_is_provided(cls, language, values, **kwargs):
        if 'filter' in values:
            if FILTERS[values['filter']].type == FilterType.BILINGUAL and language is not None:
                raise ValueError('Cannot `language` attribute for a bilingual filter')
            elif FILTERS[values['filter']].type == FilterType.MONOLINGUAL and language is None:
                raise ValueError('`language` attribute required for a monolingual filter')
        return language


def list_filters(path) -> Iterable[Filter]:
    for filename in glob(path, recursive=True):
        try:
            with open(filename) as fh:
                defaults = {
                    "name": os.path.splitext(os.path.basename(filename))[0],
                    "basedir": os.path.dirname(filename)
                }
                yield parse_obj_as(Filter, {**defaults, **json.load(fh)})
        except Exception as e:
            print(f"Could not parse {filename}: {e}", file=sys.stderr)


FILTERS: Dict[str,Filter] = {}

def reload_filters():
    global FILTERS
    FILTERS = {definition.name: definition for definition in list_filters(FILTER_PATH)}

reload_filters()


T = TypeVar("T")

def none_throws(optional: Optional[T], message: str = "Unexpected `None`") -> T:
    """Convert an optional to its value. Raises an `AssertionError` if the
    value is `None`"""
    if optional is None:
        raise AssertionError(message)
    return optional


def dataset_path(name:str, template:str):
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


def sample_path(name:str, langs: Iterable[str]):
    languages = '.'.join(sorted(langs))
    return dataset_path(name, f'.sample.{{}}.{languages}')


def filter_configuration_path(name:str) -> str:
    return dataset_path(name, '{}.filters.json')


async def compute_sample(name:str, columns:List[Tuple[str,File]]):
    langs = [lang for lang, _ in columns]
    with TemporaryFile() as tempfile:  # type: ignore[name-defined]
        proc = await asyncio.subprocess.create_subprocess_exec(
            SAMPLE_PY,
            '-n', str(SAMPLE_SIZE),
            *[str(file.resolve()) for _, file in columns],
            stdout=tempfile,
            stderr=asyncio.subprocess.PIPE)

        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise Exception(f'sample.py returned {proc.returncode}: {stderr.decode()}')

        tempfile.seek(0)

        with open(sample_path(name, langs), 'wb') as fdest:
            copyfileobj(tempfile, fdest)


class FilterOutput(BaseModel):
    stdout: List[Dict[str,str]]
    stderr: Optional[str]

    def __init__(self, langs:List[str], pairs:List[List[str]], stderr:Optional[str] = None):
        super().__init__(
            stdout=[dict(zip(langs, pair)) for pair in pairs],
            stderr=stderr)


async def get_sample(name:str, filters:List[FilterStep]) -> AsyncIterator[FilterOutput]:
    columns: List[Tuple[str,Path]] = sorted(list_datasets(DATA_PATH)[name].items(), key=lambda pair: pair[0])
    langs = [lang for lang, _ in columns]

    # If we don't have a sample stored, generate one. Doing it in bytes because
    # it might save us parsing utf-8 (also assumptions! It it utf-8?)
    if not os.path.exists(sample_path(name, langs)):
        await compute_sample(name, columns)

    with open(sample_path(name, langs), 'rb') as fh:
        sample = fh.read()

    pairs = [
        line.split('\t', maxsplit=1)
        for line in sample.decode().split('\n')
        if line.strip() != ""
    ]

    yield FilterOutput(langs, pairs)

    for i, filter_step in enumerate(filters):
        filter_definition = FILTERS[filter_step.filter]

        filter_env = {}
        for name, props in filter_definition.parameters.items():
            filter_env[name] = props.export(filter_step.parameters[name])

        # instantiate actual filter
        filter_inst = getattr(opusfilters, filter_definition.name)(**filter_env)

        scores = filter_inst.score(pairs)

        pairs = [pair for pair, score in zip(pairs, scores) if filter_inst.accept(score)]

        yield FilterOutput(langs, pairs)


def stream_jsonl(iterable):
    return StreamingResponse(
        (
            json.dumps(jsonable_encoder(line), separators=(',', ':')).encode() + b"\n"
            async for line in iterable
        ),
        media_type='application/json')


class JSFiles(StaticFiles):
    """Like StaticFiles, but if you try to access "thingy", and "thingy.js"
    exists, it will redirect to that one. Just like unpkg.com!"""

    async def get_response(self, path: str, scope: Scope) -> Response:
        # Check if file exists
        full_path_js, stat_result = await anyio.to_thread.run_sync(self.lookup_path, path)

        # if not, and it isn't already suffixed with .js, try that
        if not stat_result and not path.endswith('.js'):
            full_path_js, stat_result = await anyio.to_thread.run_sync(self.lookup_path, path + ".js")
            if stat_result:
                url = URL(scope=scope)
                url = url.replace(path=url.path + ".js")
                return RedirectResponse(url=url)

        return await super().get_response(path, scope)


app = FastAPI()

app.mount('/static/vendor', JSFiles(directory='static/vendor'), name='static/vendor')

app.mount('/static', StaticFiles(directory='static'), name='static')


@app.get('/datasets/')
def api_list_datasets() -> List[Dataset]:
    return [
        Dataset(name=name, columns={
            lang: File(path=file.name, size=file.stat().st_size)
            for lang, file in columns.items()
        })
        for name, columns in list_datasets(DATA_PATH).items()
    ]


@app.get('/datasets/{name:path}/')
def api_get_dataset(name:str) -> Dataset:
    columns = list_datasets(DATA_PATH).get(name)

    if not columns:
        raise HTTPException(status_code=404, detail='Dataset not found')

    return Dataset(name=name, columns={
        lang: File(path=file.name, size=file.stat().st_size)
        for lang, file in columns.items()
    })


@app.get('/datasets/{name:path}/sample')
async def api_get_sample(name:str) -> AsyncIterator[FilterOutput]:
    return stream_jsonl(get_sample(name, []))


@app.post('/datasets/{name:path}/sample')
async def api_get_filtered_sample(name:str, filters:List[FilterStep]) -> AsyncIterator[FilterOutput]:
    return stream_jsonl(get_sample(name, filters))


@app.get('/datasets/{name:path}/configuration.json')
def api_get_dataset_filters(name:str) -> List[FilterStep]:
    if not os.path.exists(filter_configuration_path(name)):
        return []

    with open(filter_configuration_path(name), 'r') as fh:
        return parse_obj_as(List[FilterStep], json.load(fh))


@app.post('/datasets/{name:path}/configuration.json')
def api_update_dataset_filters(name:str, filters:List[FilterStep]):
    with open(filter_configuration_path(name), 'w') as fh:
        return json.dump([step.dict() for step in filters], fh)


@app.get('/filters/')
def api_get_filters():
    reload_filters()
    return FILTERS


@app.get('/')
def redirect_to_interface():
    return RedirectResponse('/static/index.html')


def main_serve(args):
    import uvicorn
    uvicorn.run('main:app', port=args.port, reload=args.reload, log_level='info')


async def sample_all_datasets(args):
    tasks = []

    for name, columns in list_datasets(DATA_PATH).items():
        sorted_cols = sorted(columns.items(), key=lambda pair: pair[0])
        langs = [lang for lang, _ in columns]
        if not os.path.exists(sample_path(name, langs)):
            print(f"Sampling {name}...", file=sys.stderr)
            tasks.append([name, sorted_cols])

    for task, result in zip(tasks, await asyncio.gather(*[compute_sample(*task) for task in tasks], return_exceptions=True)):
        if isinstance(result, Exception):
            print(f"Could not compute sample for {task[0]}: {result!s}", file=sys.stderr)


def main_sample(args):
    asyncio.run(sample_all_datasets(args))


def main_list_commands(args):
    print("Error: No command specified.\n\n"
          "Available commands:\n"
          "  serve      run webserver\n"
          "  sample     sample all datasets\n"
          "", file=sys.stderr)
    sys.exit(1)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Fill up those seats on your empty train.')
    parser.set_defaults(func=main_list_commands)
    subparsers = parser.add_subparsers()

    parser_serve = subparsers.add_parser('serve')
    parser_serve.add_argument('-p', '--port', type=int, default=8000, help='Bind socket to this port. (default: 8000)')
    parser_serve.add_argument('--reload', action='store_true', help='Enable auto-reload.')
    parser_serve.set_defaults(func=main_serve)

    parser_sample = subparsers.add_parser('sample')
    parser_sample.set_defaults(func=main_sample)

    args = parser.parse_args()
    args.func(args)
