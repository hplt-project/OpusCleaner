import os
import sys
import subprocess

from pprint import pformat
from fnmatch import fnmatch
from typing import Dict, Any, Iterable
from hatchling.builders.hooks.plugin.interface import BuildHookInterface


def listdir_recursive(root:str='.', pattern:str='*') -> Iterable[str]:
    for entry in os.scandir(root):
        if entry.is_dir():
            yield from listdir_recursive(entry.path, pattern)
        elif fnmatch(entry.name, pattern):
            yield entry.path


class CustomBuildHook(BuildHookInterface):
    PLUGIN_NAME = 'custom'

    def initialize(self, version:str, build_data:Dict[str,Any]) -> None:
        code_path = os.path.join(self.root, self.config.get('code', '.'))
        dist_path = os.path.join(code_path, 'dist')

        subprocess.check_call(['npm','ci'], cwd=code_path)
        subprocess.check_call(['npm','run','build'], cwd=code_path)

        output = list(listdir_recursive(dist_path))

        if len(output) == 0:
            raise Exception('no ouput?!')

        build_data['force_include'].update({
            path: os.path.join('/opuscleaner/frontend/', path.removeprefix(dist_path).lstrip('/')) for
            path in output
        })
