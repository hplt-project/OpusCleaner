import json
import os
import re
import threading
from contextlib import contextmanager
from enum import Enum
from glob import glob
from shlex import quote
from typing import Optional, Iterable, Union, Literal, Any, List, Dict, Iterator
from warnings import warn

import yaml
from pydantic import BaseModel, parse_obj_as, validator

from opuscleaner.config import COL_PY
from opuscleaner._util import none_throws


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
    default: Optional[List[Any]]

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
    default: Optional[List[Any]]

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
    basedir: str
    parameters: Dict[str,FilterParameter]

    @validator('parameters')
    def check_keys(cls, parameters: Dict[str,Any]) -> Dict[str,Any]:
        for var_name in parameters.keys():
            if not re.match(r"^[a-zA-Z_][a-zA-Z_0-9]*$", var_name):
                raise ValueError(f"Parameter name is not a valid bash variable: {var_name}")
        return parameters


_FILTERS: Dict[str,Filter] = {}


class FilterStep(BaseModel):
    filter: str
    parameters: Dict[str,Any]
    language: Optional[str]

    @validator('filter')
    def check_filter(cls, filter_name:str) -> str:
        global _FILTERS
        if _FILTERS and filter_name not in _FILTERS:
            raise ValueError(f'Unknown filter: `{filter_name}`')
        return filter_name

    @validator('parameters')
    def check_parameters(cls, parameters:Dict[str,Any], values:Dict[str,Any], **kwargs) -> Dict[str,Any]:
        global _FILTERS
        if _FILTERS and 'filter' in values:
            required = set(_FILTERS[values['filter']].parameters.keys())
            provided = set(parameters.keys())

            missing_keys = required - provided
            if missing_keys:
                warn(f"Missing filter parameters: {' '.join(missing_keys)}")
                # Just add their default values in that case.
                parameters |= {
                    key: parameter.default if hasattr(parameter, 'default') and parameter.default is not None else parameter.default_factory()
                    for key, parameter in _FILTERS[values['filter']].parameters.items()
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
    def check_language_is_provided(cls, language:str, values:Dict[str,Any], **kwargs) -> str:
        if _FILTERS and 'filter' in values:
            if _FILTERS[values['filter']].type == FilterType.BILINGUAL and language is not None:
                raise ValueError('Cannot `language` attribute for a bilingual filter')
            elif _FILTERS[values['filter']].type == FilterType.MONOLINGUAL and language is None:
                raise ValueError('`language` attribute required for a monolingual filter')
        return language


class FilterPipeline(BaseModel):
    version: Literal[1]
    files: List[str]
    filters: List[FilterStep]


def list_filters(paths:str) -> Iterable[Filter]:
    for path in paths.split(os.pathsep):
        for filename in glob(path, recursive=True):
            try:
                with open(filename) as fh:
                    defaults = {
                        "name": os.path.splitext(os.path.basename(filename))[0],
                        "basedir": os.path.dirname(filename)
                    }
                    yield parse_obj_as(Filter, {**defaults, **json.load(fh)})
            except Exception as e:
                warn(f"Could not parse {filename}: {e}")


def set_global_filters(filters:Iterable[Filter]) -> None:
    global _FILTERS
    _FILTERS = {filter.name: filter for filter in filters}


def get_global_filters() -> Dict[str,Filter]:
    global _FILTERS
    return _FILTERS


def get_global_filter(name:str) -> Filter:
    return get_global_filters()[name]


def format_shell(val: Any) -> str:
    if isinstance(val, bool):
        return '1' if val else ''
    elif isinstance(val, tuple):
        raise NotImplementedError()
    elif isinstance(val, list):
        raise NotImplementedError()
    else:
        return str(val)


def filter_format_command(filter_definition:Filter, filter_step:FilterStep, langs:List[str], *, path_to_col:List[str]=COL_PY) -> str:
    if filter_definition.type == FilterType.BILINGUAL:
        command = filter_definition.command
    elif filter_definition.type == FilterType.MONOLINGUAL:
        columns = [langs.index(language) for language in none_throws(filter_step.language).split(',')]
        command = f'{" ".join(map(quote, path_to_col))} {",".join(map(str, columns))} {filter_definition.command}'
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

    return command
