#!/usr/bin/env python3
import os
import gzip
from shlex import quote
import sys
import re
from typing import NamedTuple, Optional, Iterable, TypeVar, Union, Literal, Any, AsyncIterator, Awaitable, cast, IO, List, Dict, Tuple
from contextlib import ExitStack
from itertools import chain, zip_longest
from pydantic import BaseModel, parse_obj_as, validator, ValidationError
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
import yaml
from glob import glob
from tempfile import TemporaryFile
from shutil import copyfileobj
from pprint import pprint
from warnings import warn
from copy import deepcopy

from datasets import list_datasets, Path
from download import app as download_app
from categories import app as categories_app
from config import DATA_PATH, FILTER_PATH, COL_PY, SAMPLE_PY, SAMPLE_SIZE
from sample import sample

import mimetypes
mimetypes.add_type('application/javascript', '.js')


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

    def export(self, value: Any) -> Any:
        return str(value)

    def default_factory(self) -> Any:
        return None


class FilterParameterFloat(FilterParameterBase):
    type: Literal["float"]
    min: Optional[float]
    max: Optional[float]
    default: Optional[float]

    def export(self, value: Any) -> Any:
        return float(value)


class FilterParameterInt(FilterParameterBase):
    type: Literal["int"]
    min: Optional[int]
    max: Optional[int]
    default: Optional[int]

    def export(self, value: Any) -> Any:
        return int(value)


class FilterParameterBool(FilterParameterBase):
    type: Literal["bool"]
    default: Optional[bool]

    def export(self, value: Any) -> Any:
        return bool(value)


class FilterParameterStr(FilterParameterBase):
    type: Literal["str"]
    default: Optional[str]
    allowed_values: Optional[List[str]]

    def export(self, value: Any) -> Any:
        # TODO: validate against allowed_values?
        return super().export(value)

    def default_factory(self) -> Any:
        return ''


class FilterParameterList(FilterParameterBase):
    type: Literal["list"]
    parameter: "FilterParameter"
    default: Optional[List]

    def export(self, value: Any) -> Any:
        return [
            self.parameter.export(item)
            for item in value
        ]

    def default_factory(self) -> Any:
        return []


class FilterParameterTuple(FilterParameterBase):
    type: Literal["tuple"]
    parameters: List["FilterParameter"]
    default: Optional[List]

    # TODO: Add validator that checks if len(default) == len(parameters)

    def export(self, value: Any) -> Any:
        return tuple(
            parameter.export(val)
            for parameter, val in zip(self.parameters, value)
        )

    def default_factory(self) -> Any:
        return [
            parameter.default_factory()
            for parameter in self.parameters
        ]


FilterParameter = Union[
    FilterParameterFloat,
    FilterParameterInt,
    FilterParameterBool,
    FilterParameterStr,
    FilterParameterList,
    FilterParameterTuple
]

FilterParameterList.update_forward_refs()
FilterParameterTuple.update_forward_refs()


class Filter(BaseModel):
    type: FilterType
    name: str # comes from filename by default
    description: Optional[str]
    command: str
    basedir: Optional[str] # same as .json file by default
    parameters: Dict[str,FilterParameter]

    @validator('parameters')
    def check_keys(cls, parameters):
        for var_name in parameters.keys():
            if not re.match(r"^[a-zA-Z_][a-zA-Z_0-9]*$", var_name):
                raise ValueError(f"Parameter name is not a valid bash variable: {var_name}")
        return parameters


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

            missing_keys = required - provided
            if missing_keys:
                warn(f"Missing filter parameters: {' '.join(missing_keys)}")
                # Just add their default values in that case.
                parameters |= {
                    key: parameter.default if hasattr(parameter, 'default') and parameter.default is not None else parameter.default_factory()
                    for key, parameter in FILTERS[values['filter']].parameters.items()
                    if key in missing_keys
                }
            
            superfluous_keys = provided - required
            if superfluous_keys:
                warn(f"Provided parameters not supported by the filter: {' '.join(superfluous_keys)}")
                # Not doing anything though, might be that we have just loaded an
                # old version of the filter definition and we don't want to lose
                # any of these keys.

        return parameters

    @validator('language', always=True)
    def check_language_is_provided(cls, language, values, **kwargs):
        if 'filter' in values:
            if FILTERS[values['filter']].type == FilterType.BILINGUAL and language is not None:
                raise ValueError('Cannot `language` attribute for a bilingual filter')
            elif FILTERS[values['filter']].type == FilterType.MONOLINGUAL and language is None:
                raise ValueError('`language` attribute required for a monolingual filter')
        return language


class FilterPipeline(BaseModel):
    version: Literal[1]
    files: List[str]
    filters: List[FilterStep]


def list_filters(paths) -> Iterable[Filter]:
    for path in paths.split(':'):
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


async def compute_sample(name:str, columns:List[Tuple[str,Path]]):
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


async def get_dataset_sample(name, columns) -> Tuple[bytes,bytes]:
    langs = [lang for lang, _ in columns]

    if not os.path.exists(sample_path(name, langs)):
        await compute_sample(name, columns)

    with open(sample_path(name, langs), 'rb') as fh:
        return fh.read(), bytes()


class FilterOutput(BaseModel):
    stdout: List[Dict[str,str]]
    stderr: Optional[str]

    def __init__(self, langs:List[str], stdout:bytes, stderr:Optional[bytes] = None):
        lines = []

        for lineno, line in enumerate(stdout.rstrip(b'\n').split(b'\n'), start=1):
            values = []
            for colno, field in enumerate(line.split(b'\t'), start=1):
                try:
                    values.append(field.decode())
                except UnicodeDecodeError as e:
                    values.append(f'[Error: Cannot decode line {lineno} column {colno}: {e!s}]')
            lines.append(dict(zip_longest(langs, values, fillvalue='')))

        super().__init__(
            stdout=lines,
            stderr=stderr.decode() if stderr is not None else None)


class SampleCacheEntry(NamedTuple):
    checksum: bytes
    future: asyncio.Task[Tuple[bytes, bytes]]


sample_cache: Dict[str,List[SampleCacheEntry]] = {}


def cache_hash(obj: Any, seed: bytes = bytes()) -> bytes:
    impl = hashlib.sha256(seed)
    impl.update(json.dumps(obj, sort_keys=True).encode())
    return impl.digest()


def format_shell(val: Any) -> str:
    if isinstance(val, bool):
        return '1' if val else ''
    elif isinstance(val, tuple):
        raise NotImplementedError()
    elif isinstance(val, list):
        raise NotImplementedError()
    else:
        return str(val)


async def exec_filter_step(filter_step: FilterStep, langs: List[str], input: bytes) -> Tuple[bytes,bytes]:
    filter_definition = FILTERS[filter_step.filter]

    if filter_definition.type == FilterType.BILINGUAL:
            command = filter_definition.command
    elif filter_definition.type == FilterType.MONOLINGUAL:
        column = langs.index(none_throws(filter_step.language))
        command = f'{COL_PY} {column} {filter_definition.command}'
    else:
        raise NotImplementedError()

    if filter_definition.parameters:
        params = {
            name: props.export(filter_step.parameters[name])
            for name, props in filter_definition.parameters.items()
        }
        if 'PARAMETERS_AS_YAML' in command:
            command = f'PARAMETERS_AS_YAML={quote(yaml.safe_dump(params))}; {command}'
        else:
            vars_setter = '; '.join(f"{k}={quote(format_shell(v))}" for k, v in params.items())
            command = f'{vars_setter}; {command}'

    print(command, file=sys.stderr)

    p_filter = await asyncio.create_subprocess_shell(command,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=filter_definition.basedir)

    # Check exit codes, testing most obvious problems first.
    return await p_filter.communicate(input=input)


def cancel_cached_tasks(name:str, offset:int):
    for entry in sample_cache[name][offset:]:
        entry.future.cancel()
    del sample_cache[name][offset:]


async def get_sample(name:str, filters:List[FilterStep]) -> AsyncIterator[FilterOutput]:
    columns: List[Tuple[str,Path]] = sorted(list_datasets(DATA_PATH)[name].items(), key=lambda pair: pair[0])
    langs = [lang for lang, _ in columns]

    checksum = cache_hash([
        (name, str(path), path.stat().st_mtime)
        for name, path in columns
    ])

    # If we don't have a sample stored, generate one. Doing it in bytes because
    # it might save us parsing utf-8 (also assumptions! It it utf-8?)
    if not name in sample_cache or sample_cache[name][0].checksum != checksum:
        sample_cache[name] = [
            SampleCacheEntry(
                checksum=checksum,
                future=asyncio.create_task(get_dataset_sample(name, columns))
            )
        ]

    sample, _ = await sample_cache[name][0].future

    yield FilterOutput(langs, sample)

    for i, filter_step in enumerate(filters, start=1):
        filter_definition = FILTERS[filter_step.filter]

        checksum = cache_hash(jsonable_encoder(filter_step),
            cache_hash(jsonable_encoder(filter_definition),
                sample_cache[name][i-1].checksum))

        # If we do not have a cache entry for this point
        if len(sample_cache[name]) <= i or sample_cache[name][i].checksum != checksum:
            # Invalidate all the cache after this step
            cancel_cached_tasks(name, i)

            sample_cache[name].append(SampleCacheEntry(
                checksum=checksum,
                future=asyncio.create_task(exec_filter_step(filter_step, langs, sample))
            ))

            assert len(sample_cache[name]) == i + 1
        
        filter_output, filter_stderr = await sample_cache[name][i].future    
        
        yield FilterOutput(langs, filter_output, filter_stderr)

        sample = filter_output

    # if there are additional steps left in the cache, remove them
    if len(sample_cache[name]) > len(filters) + 1:
        cancel_cached_tasks(name, len(filters) + 1)


def stream_jsonl(iterable):
    return StreamingResponse(
        (
            json.dumps(jsonable_encoder(line), separators=(',', ':')).encode() + b"\n"
            async for line in iterable
        ),
        media_type='application/json')


app = FastAPI()

@app.get('/api/datasets/')
def api_list_datasets() -> List[Dataset]:
    return [
        Dataset(name=name, columns={
            lang: File(path=file.name, size=file.stat().st_size)
            for lang, file in columns.items()
        })
        for name, columns in list_datasets(DATA_PATH).items()
    ]


@app.get('/api/datasets/{name:path}/')
def api_get_dataset(name:str) -> Dataset:
    columns = list_datasets(DATA_PATH).get(name)

    if not columns:
        raise HTTPException(status_code=404, detail='Dataset not found')

    return Dataset(name=name, columns={
        lang: File(path=file.name, size=file.stat().st_size)
        for lang, file in columns.items()
    })


@app.get('/api/datasets/{name:path}/sample')
async def api_get_sample(name:str) -> AsyncIterator[FilterOutput]:
    return stream_jsonl(get_sample(name, []))


@app.post('/api/datasets/{name:path}/sample')
async def api_get_filtered_sample(name:str, filters:List[FilterStep]) -> AsyncIterator[FilterOutput]:
    return stream_jsonl(get_sample(name, filters))


@app.get('/api/datasets/{name:path}/configuration.json')
def api_get_dataset_filters(name:str) -> List[FilterStep]:
    if not os.path.exists(filter_configuration_path(name)):
        return []

    with open(filter_configuration_path(name), 'r') as fh:
        data = json.load(fh)
        try:
            return parse_obj_as(FilterPipeline, data).filters
        except ValidationError:
            # Backwards compatibility
            return parse_obj_as(List[FilterStep], data)


def select_filter_steps(pattern: str, pipeline: FilterPipeline) -> List[Dict[str,Dict]]:
    return [
        {str(re.search(pattern, FILTERS[step.filter].command).group(1)): step.parameters}
        for step in pipeline.filters
        if re.search(pattern, FILTERS[step.filter].command) is not None
    ]


@app.get('/api/datasets/{name:path}/configuration-for-opusfilter.yaml')
def api_get_dataset_filters_as_openfilter(name:str) -> List[FilterStep]:
    if not os.path.exists(filter_configuration_path(name)):
        return []

    with open(filter_configuration_path(name), 'r') as fh:
        data = json.load(fh)

    pipeline = parse_obj_as(FilterPipeline, data)

    opusfilter_config = {
        'steps': []
    }

    input_files = pipeline.files
    
    preprocess_steps = select_filter_steps(r'\bopusfilter\.preprocessors\.(\w+)\b', pipeline)

    if preprocess_steps:
        output_files = [
            os.path.join(os.path.dirname(file), 'preprocessed.' + os.path.basename(file))
            for file in pipeline.files
        ]

        opusfilter_config['steps'].append({
            'type': 'filter',
            'parameters': {
                'inputs': input_files,
                'outputs': output_files,
                'preprocessors': preprocess_steps
            }
        })

        input_files = output_files

    filter_steps = select_filter_steps(r'\bopusfilter\.filters\.(\w+)\b', pipeline)

    if filter_steps:
        output_files = [
            os.path.join(os.path.dirname(file), 'filtered.' + os.path.basename(file))
            for file in pipeline.files
        ]

        opusfilter_config['steps'].append({
            'type': 'filter',
            'parameters': {
                'inputs': input_files,
                'outputs': output_files,
                'filters': filter_steps
            }
        })

        input_files = output_files

    return Response(yaml.safe_dump(opusfilter_config, sort_keys=False), media_type='application/yaml')

@app.post('/api/datasets/{name:path}/configuration.json')
def api_update_dataset_filters(name:str, filters:List[FilterStep]):
    columns = list_datasets(DATA_PATH)[name]

    pipeline = FilterPipeline(
        version=1,
        files=[file.name
            for _, file in
            sorted(columns.items(), key=lambda pair: pair[0])
        ],
        filters=filters
    )

    with open(filter_configuration_path(name), 'w') as fh:
        return json.dump(pipeline.dict(), fh, indent=2)


@app.get('/api/filters/')
def api_get_filters():
    reload_filters()
    return FILTERS


@app.get('/')
def redirect_to_interface():
    return RedirectResponse('/frontend/index.html')


app.mount('/frontend/', StaticFiles(directory='frontend/dist', html=True), name='static')

app.mount('/api/download/', download_app)

app.mount('/api/categories/', categories_app)

def main_serve(args):
    import uvicorn
    uvicorn.run(f'main:app', port=args.port, reload=args.reload, log_level='info')


async def sample_all_datasets(args):
    tasks = []

    for name, columns in list_datasets(DATA_PATH).items():
        sorted_cols = sorted(columns.items(), key=lambda pair: pair[0])
        langs = [lang for lang, _ in sorted_cols]
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
