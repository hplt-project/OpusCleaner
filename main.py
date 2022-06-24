import os
import gzip
import sys
from typing import Optional, Iterable, TypeVar, Union, Literal, Any
from contextlib import ExitStack
from itertools import chain
from pydantic import BaseModel, parse_obj_as, validator
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from enum import Enum
import json
import subprocess
import hashlib
from glob import glob
from tempfile import TemporaryFile
from shutil import copyfileobj

from datasets import list_datasets
from sample import sample


DATA_PATH = 'data/train-parts'

FILTER_PATH = 'filters/*.json'

# col.py is used to apply a monolingual filter to a bilingual dataset. Needs
# to be absolute since filters can run from different cwds.
COL_PY = os.path.abspath('./col.py')


class File(BaseModel):
    path: str
    size: int


class Dataset(BaseModel):
    name: str
    columns: dict[str,File]


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


class FilterParameterInt(FilterParameterBase):
    type: Literal["int"]
    min: Optional[int]
    max: Optional[int]
    default: Optional[int]


class FilterParameterBool(FilterParameterBase):
    type: Literal["bool"]
    default: Optional[bool]

    def export(self, value: Any) -> str:
        return "1" if value else ""


class FilterParameterStr(FilterParameterBase):
    type: Literal["str"]
    default: Optional[str]
    allowed_values: Optional[list[str]]


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
    parameters: dict[str,FilterParameter]


class FilterStep(BaseModel):
    filter: str
    parameters: dict[str,Any]
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



FILTERS: dict[str,Filter] = {}

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


class FilterOutput(BaseModel):
    stdout: list[dict[str,str]]
    stderr: Optional[str]


def get_sample(name:str, filters:list[FilterStep]) -> FilterOutput:
    columns: list[tuple[str,os.DirEntry]] = sorted(list_datasets(DATA_PATH)[name].items(), key=lambda pair: pair[0])
    langs = [lang for lang, _ in columns]

    # If we don't have a sample stored, generate one. Doing it in bytes because
    # it might save us parsing utf-8 (also assumptions! It it utf-8?)
    if not os.path.exists(sample_path(name, langs)):
        compute_sample(name, columns)

    sample_file = sample_path(name, langs)

    filter_hash = ''

    p_filter_stderr:Optional[bytes] = None

    for i, filter_step in enumerate(filters):
        filter_definition = FILTERS[filter_step.filter]
        filter_json = json.dumps(filter_step.dict(), sort_keys=True)
        filter_hash = hashlib.sha256((filter_hash + filter_json).encode()).hexdigest()
        
        # If we already have this cached, skip it. Unless it is the last step,
        # we always re-execute that one for debug output etc.
        if not os.path.exists(sample_path(name, langs) + filter_hash) or i + 1 == len(filters):
            with TemporaryFile('w+b') as fout:
                # Decompress input
                p_gunzip = subprocess.Popen(['pigz', '-cd', sample_file], stdout=subprocess.PIPE)

                # Compress output
                p_gzip = subprocess.Popen(['pigz', '-9c'], stdin=subprocess.PIPE, stdout=fout)

                filter_env = os.environ.copy()
                for name, props in filter_definition.parameters.items():
                    filter_env[name] = props.export(filter_step.parameters[name])

                if filter_definition.type == FilterType.BILINGUAL:
                    command = [filter_definition.command]
                elif filter_definition.type == FilterType.MONOLINGUAL:
                    column = langs.index(none_throws(filter_step.language))
                    command = [f'{COL_PY} {column} {filter_definition.command}']
                else:
                    raise NotImplementedError()
                
                p_filter = subprocess.Popen(command, env=filter_env, stdin=p_gunzip.stdout, stdout=p_gzip.stdin, stderr=subprocess.PIPE, shell=True, cwd=filter_definition.basedir)
                
                # Disconnect from the pipes only used by the spawned processes
                none_throws(p_gunzip.stdout).close()
                none_throws(p_gzip.stdin).close()

                # Check exit codes, testing most obvious problems first.
                _, p_filter_stderr = p_filter.communicate()
                if p_filter.returncode != 0:
                    raise Exception(f"Step {i}: {filter_step.filter} failed:\n{p_filter_stderr!s}")

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
        return FilterOutput(
            stdout=[dict(zip(langs, line.rstrip('\n').split('\t'))) for line in fh],
            stderr=p_filter_stderr.decode() if p_filter_stderr is not None else None)


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
def api_get_dataset(name:str) -> FilterOutput:
    return get_sample(name, [])


@app.post('/datasets/{name}/sample')
def api_get_filtered_dataset(name:str, filters:list[FilterStep]) -> FilterOutput:
    return get_sample(name, filters)


@app.get('/filters/')
def api_get_filters():
    reload_filters()
    return FILTERS


@app.get('/')
def redirect_to_interface():
    return RedirectResponse('/static/index.html')

