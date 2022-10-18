#!/usr/bin/env python3
import os
import gzip
from shlex import quote
import sys
import re
from typing import Optional, Iterable, TypeVar, Union, Literal, Any, AsyncIterator, cast, IO, List, Dict, Tuple
from contextlib import ExitStack
from itertools import chain
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
import importlib
import opusfilter
from glob import glob
from tempfile import TemporaryFile
from shutil import copyfileobj
from pprint import pprint


from datasets import list_datasets, Path
from download import app as download_app
from sample import sample

import mimetypes
mimetypes.add_type('application/javascript', '.js')


DATA_PATH = os.getenv('DATA_PATH', 'data/train-parts/*.*.gz')

FILTER_PATH = 'filters/*.json'

# col.py is used to apply a monolingual filter to a bilingual dataset. Needs
# to be absolute since filters can run from different cwds.
COL_PY = os.path.abspath('./col.py')

SAMPLE_PY = os.path.abspath('./sample.py')

# Size of each of the three sections (head, random sample of middle, tail) of
# the dataset sample that we operate on.
SAMPLE_SIZE = int(os.getenv('SAMPLE_SIZE', '1000'))


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


class FilterParameterList(FilterParameterBase):
    type: Literal["list"]
    parameter: "FilterParameter"

    def export(self, value: Any) -> Any:
        return [
            self.parameter.export(item)
            for item in value
        ]


class FilterParameterTuple(FilterParameterBase):
    type: Literal["tuple"]
    parameters: List["FilterParameter"]

    def export(self, value: Any) -> Any:
        return tuple(
            parameter.export(val)
            for parameter, val in zip(self.parameters, value)
        )


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


class FilterPipeline(BaseModel):
    version: Literal[1]
    files: List[str]
    filters: List[FilterStep]


# def list_filters(path) -> Iterable[Filter]:
#     for filename in glob(path, recursive=True):
#         try:
#             with open(filename) as fh:
#                 defaults = {
#                     "name": os.path.splitext(os.path.basename(filename))[0],
#                     "basedir": os.path.dirname(filename)
#                 }
#                 yield parse_obj_as(Filter, {**defaults, **json.load(fh)})
#         except Exception as e:
#             print(f"Could not parse {filename}: {e}", file=sys.stderr)


def list_filters(path) -> Iterable[Filter]:
    filters = [
        {
            'type': 'bilingual',
            'name': 'LengthFilter',
            'command': 'opusfilter.filters.LengthFilter',
            'description': 'Sentence length filter',
            'parameters': {
                'min_length': {
                    'type': 'int',
                    'default': 1
                },
                'max_lenght': {
                    'type': 'int',
                    'default': 100
                },
                'unit': {
                    'type': 'str',
                    'allowed_values': ['word', 'character']
                },
                'pass_empty': {
                    'type': 'bool',
                    'default': False
                }
            }
        },
        {
            'type': 'bilingual',
            'name': 'LengthRatioFilter',
            'command': 'opusfilter.filters.LengthRatioFilter',
            'description': 'Character length ratio',
            'parameters': {
                'threshold': {
                    'type': 'int',
                    'default': 3
                },
                'unit': {
                    'type': 'str',
                    'default': 'word',
                    'allowed_values': ['word', 'character']
                }
            }
        },
        {
            'type': 'bilingual',
            'name': 'LongWordFilter',
            'command': 'opusfilter.filters.LongWordFilter',
            'description': 'Word length filter',
            'parameters': {
                'threshold': {
                    'type': 'int',
                    'default': 40
                }
            }
        },
        {
            'type': 'bilingual',
            'name': 'AverageWordLengthFilter',
            'command': 'opusfilter.filters.AverageWordLengthFilter',
            'description': 'Average word length filter. Returns zeros for empty segments. If pass_empty is true, pairs with only empty segments are accepted.',
            'parameters': {
                'min_length': {
                    'type': 'int',
                    'default': 1
                },
                'max_lenght': {
                    'type': 'int',
                    'default': 100
                },
                'pass_empty': {
                    'type': 'bool',
                    'default': False
                }
            }
        },
        {
            'type': 'bilingual',
            'name': 'HtmlTagFilter',
            'command': 'opusfilter.filters.HtmlTagFilter',
            'description': 'HTML tag filter',
            'parameters': {}
        },
        {
            'type': 'bilingual',
            'name': 'RegExpFilter',
            'command': 'opusfilter.filters.RegExpFilter',
            'description': 'Filter out segments that match or do not match a regular expression',
            'parameters': {
                'regexps': {
                    'type': 'tuple',
                    'help': 'Regexp pattern for each language in the parallel data.',
                    'parameters': [
                        {
                            'type': 'str',
                            'help': 'Pattern matching first column'
                        },
                        {
                            'type': 'str',
                            'help': 'Pattern matching second column'
                        }
                    ]
                },
                'accept_match': {
                    'type': 'bool',
                    'default': False,
                    'help': 'If accept_match is False, the pair is accepted only if none of the segment match the corresponding regexp. If accept_match is True, the pair is accepted only if all segments match the corresponding regexp.'
                }
            }
        },
        {
            'type': 'bilingual',
            'name': 'AlphabetRatioFilter',
            'command': 'opusfilter.filters.AlphabetRatioFilter',
            'description': 'Proportion of alphabetic characters in the segment',
            'parameters': {
                'threshold': {
                    'type': 'float',
                    'default': 0.75
                },
                'exclude_whitespace': {
                    'type': 'bool',
                    'default': False
                }
            }
        },
        {
            'type': 'bilingual',
            'name': 'CharacterScoreFilter',
            'command': 'opusfilter.filters.CharacterScoreFilter',
            'description': 'Proportion of alphabetic characters that are in the given script.',
            'parameters': {
                'scripts': {
                    'type': 'tuple',
                    'help': 'For a list of valid scripts, see https://www.regular-expressions.info/unicode.html',
                    'parameters': [
                        {
                            'type': 'str'
                        },
                        {  
                            'type': 'str'
                        }
                    ]
                },
                'thresholds': {
                    'type': 'tuple',
                    'parameters': [
                        {
                            'type': 'float',
                            'default': 1
                        },
                        {  
                            'type': 'float',
                            'default': 1
                        }
                    ]
                }
            }
        }
    ]

    filters += [
        {
            "type": "bilingual",
            "name": "Tokenizer",
            "description": "Tokenize text",
            "command": "opusfilter.preprocessors.Tokenizer",
            "parameters": {
                "tokenizer": {
                    "type": "tuple",
                    "parameters": [
                        {
                            "type": "str",
                            "allowed_values": ["moses", "jieba", "mecab"],
                            "default": "moses"
                        },
                        {
                            "type": "str",
                            "allowed_values": ["moses", "jieba", "mecab"],
                            "default": "moses"
                        }
                    ]
                },
                "languages": {
                    "type": "tuple",
                    "parameters": [
                        {
                            "type": "str"
                        },
                        {
                            "type": "str"
                        }
                    ]
                }
            }
        },
        {
            "type": "bilingual",
            "name": "Detokenizer",
            "description": "Detokenize text",
            "command": "opusfilter.preprocessors.Detokenizer",
            "parameters": {
                "tokenizer": {
                    "type": "tuple",
                    "parameters": [
                        {
                            "type": "str",
                            "allowed_values": ["moses", "jieba", "mecab"],
                            "default": "moses"
                        },
                        {
                            "type": "str",
                            "allowed_values": ["moses", "jieba", "mecab"],
                            "default": "moses"
                        }
                    ]
                },
                "languages": {
                    "type": "tuple",
                    "parameters": [
                        {
                            "type": "str"
                        },
                        {
                            "type": "str"
                        }
                    ]
                }
            }
        },
        {
            "type": "bilingual",
            "name": "WhitespaceNormalizer",
            "description": "Normalize whitespace characters. Replace any sequences of whitespace characters with a single space and remove leading and trailing whitespace.",
            "command": "opusfilter.preprocessors.WhitespaceNormalizer",
            "parameters": {}
        },
        {
            "type": "bilingual",
            "name": "RegExpSub",
            "description": "Apply regular expression substitutions",
            "command": "opusfilter.preprocessors.RegExpSub",
            "parameters": {
                "patterns": {
                    "type": "list",
                    "parameter": {
                        "type": "tuple",
                        "parameters": [
                            {
                                "type": "str",
                                "help": "pattern"
                            },
                            {
                                "type": "str",
                                "help": "replacement"
                            },
                            {
                                "type": "int",
                                "help": "count (0 = substitute all)",
                                "default": 0
                            },
                            {
                                "type": "str",
                                "help": "flags",
                                "default": "I"
                            }
                        ]
                    }
                }
            }
        }
    ]

    return parse_obj_as(List[Filter], filters)


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

    def __init__(self, langs:List[str], stdout:Iterable[List[str]], stderr:Optional[str] = None):
        super().__init__(
            stdout=[dict(zip(langs, pairs)) for pairs in stdout],
            stderr=stderr)


async def get_sample(name:str, filters:List[FilterStep]) -> AsyncIterator[FilterOutput]:
    columns: List[Tuple[str,Path]] = sorted(list_datasets(DATA_PATH)[name].items(), key=lambda pair: pair[0])
    langs = [lang for lang, _ in columns]

    # If we don't have a sample stored, generate one. Doing it in bytes because
    # it might save us parsing utf-8 (also assumptions! It it utf-8?)
    if not os.path.exists(sample_path(name, langs)):
        await compute_sample(name, columns)

    with open(sample_path(name, langs), 'rt') as fh:
        sample = [
            line.rstrip('\n').split('\t')
            for line in fh.read()
        ]

    yield FilterOutput(langs, sample)

    for i, filter_step in enumerate(filters):
        filter_definition = FILTERS[filter_step.filter]

        if filter_definition.type == FilterType.MONOLINGUAL:
            raise NotImplementedError()

        try:
            params = {
                name: props.export(filter_step.parameters[name])
                for name, props in filter_definition.parameters.items()
            }

            module_name, class_name = filter_definition.command.rsplit('.', maxsplit=1)
            module = importlib.import_module(module_name)
            filter_cls = getattr(module, class_name)

            filter_inst = filter_cls(**params)

            if isinstance(filter_inst, opusfilter.FilterABC):
                sample = filter_inst.filter(sample)
            elif isinstance(filter_inst, opusfilter.PreprocessorABC):
                sample = filter_inst.process(sample)
            else:
                raise NotImplementedError()

            assert sample is not None
            yield FilterOutput(langs, sample)
        except Exception as err:
            yield FilterOutput(langs, [], str(err))


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
