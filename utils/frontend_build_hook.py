import subprocess
import os
from typing import Any
import logging

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


logger = logging.getLogger(__name__)


class NpmBuildHook(BuildHookInterface):
    @property
    def working_dir(self):
        return self.config.get("working_dir", ".")

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        # if we can't build because we don't have the build dir, skip
        if not os.path.exists(self.working_dir):
            logger.info(f"Skipping npm build because {self.working_dir=} does not exist")
            return
        # if we don't need to build because we have all the artifacts, skip
        if all(os.path.exists(artifact) for artifact in self.config.get("artifacts", [])):
            logger.info(f"Skipping npm build because all artifacts exist")
            return
        subprocess.check_output(
            "npm install && npm run build",
            shell=True,
            cwd=self.working_dir)

    def clean(self, versions: list[str]) -> None:
        subprocess.check_output("npm run clean", shell=True, cwd=self.working_dir)
