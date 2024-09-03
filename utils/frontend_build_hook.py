import subprocess
import os
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class NpmBuildHook(BuildHookInterface):
    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        if all(os.path.exists(artifact) for artifact in self.config.get("artifacts", [])):
            return
        subprocess.check_output(
            "npm install && npm run build",
            shell=True,
            cwd=self.config.get("working_dir", "."))

    def clean(self, versions: list[str]) -> None:
        subprocess.check_output("npm run clean", shell=True)
