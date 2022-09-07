#!/usr/bin/env python3
import inspect
import json
from opusfilter import filters, FilterABC
from pprint import pprint


def derive_filter_definition(filter_cls):
    filter_spec = inspect.getfullargspec(filter_cls.__init__)

    parameters = {}

    # pprint(filter_spec)
    for arg, default_val in zip(filter_spec.args[1:], filter_spec.defaults or []): # skipping `self`
        parameters[arg] = dict(
            type=type(default_val).__name__,
            default=default_val
        )


    return dict(
        type='bilingual',
        name=filter_cls.__name__,
        description=filter_cls.__doc__,
        command=f'opusfilter:{filter_cls.__name__}',
        parameters=parameters
    )

for filter_name, filter_cls in filters.__dict__.items():
    if isinstance(filter_cls, type) \
        and filter_cls.__module__ == filters.__name__ \
        and issubclass(filter_cls, FilterABC):
        with open(f'filters/{filter_name}.json', 'w') as fh:
            json.dump(derive_filter_definition(filter_cls), fh, indent=2)
