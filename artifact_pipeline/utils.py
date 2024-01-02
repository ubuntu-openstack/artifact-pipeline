#
# Copyright (C) 2023 Canonical Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""Utility classes and functions."""
import asyncio
import jinja2
import os
from glob import glob

from temporalio import activity


# cloud-archives that are currently receiving backports
OS_SERIES_BACKPORTING = {
    "queens": "xenial",
    "ussuri": "bionic",
    "yoga": "focal",
    "antelope": "jammy",
    "bobcat": "jammy",
    "caracal": "jammy",
}


class BuildResult:
    """Store the build results for a package build."""

    def __init__(
        self, package: str, version: str = "", status: str = "current"
    ):
        self.package = package
        self.version = version
        self.status = status
        self.output = ""
        self.logfile = ""

    def update_build_result(
        self, cmd: list[str], retcode: int, output: str, work_dir: str
    ):
        """Update the build results for a package build.

        :param cmd: Most recent command that was executed.
        :param retcode: Return code from command that was executed.
        :param output: Output from command that was executed.
        :param work_dir: Directory where package build artifacts are stored.
        """
        if not self.version:
            pkg_build_dir = glob(
                os.path.join(f"{work_dir}", f"{self.package}*")
            )
            if pkg_build_dir:
                self.version = pkg_build_dir[0].split(
                    os.path.join(f"{work_dir}", f"{self.package}-")
                )[1]

        if retcode:
            self.status = "failed"

        if output:
            formatted = (
                f"+ {' '.join(cmd)}\n{output}+ return code: {retcode}\n"
            )
            if not self.output:
                self.output = formatted
            else:
                self.output = f"{self.output}\n{formatted}"

            if self.version:
                self.logfile = f"{self.package}-{self.version}"
            else:
                self.logfile = f"{self.package}"

    def write_build_result(self, log_dir: str) -> str:
        """Write the build results output to a file.

        :param log_dir: Directory to store build log file in.
        """
        if self.output:
            logfile_path = os.path.join(log_dir, self.logfile)
            with open(logfile_path, "w") as f:
                f.write(self.output)
                self.output = ""
            return logfile_path
        return ""


async def asyncio_create_subprocess_exec(
    cmd: list[str], redirect_stderr: bool = True, env: dict[str, str] = {}
) -> tuple[int, str]:
    """Run command with asyncio.create_subprocess_exec.

    :param cmd: Command to run.
    :param redirect_stderr: Whether to redirect stderr to stdout.
    :param env: Dictionary of environment variables.
    """
    activity.logger.info(f"Running command: {cmd}")
    if redirect_stderr:
        stderr_stream = asyncio.subprocess.STDOUT
    else:
        stderr_stream = asyncio.subprocess.PIPE
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=stderr_stream,
        env=env,
    )
    stdout, stderr = await process.communicate()
    activity.logger.info(f"Command stdout: {stdout.decode()}")
    if stderr:
        activity.logger.info(f"Command stderr: {stderr.decode()}")
    return (process.returncode, stdout.decode())


def os_auth_env(novarc: str) -> dict[str, str]:
    """Translate openstack credentials file to environment variables.

    :param novarc: OpenStack credentials file name.
    """
    env = {}
    with open(novarc, "r") as f:
        for line in f.readlines():
            if "export" not in line:
                continue
            line = line.replace("export ", "")
            line = line.replace('"', "")
            line = line.rstrip()
            var = line.split("=")[0]
            val = line.split("=")[1]
            env[var] = val
    return env


def get_template_path(subpath: str = "") -> str:
    """Get full path to templates directory or templates subdirectory.

    :param subpath: Optional subdirectory.
    """
    return os.path.join(
        os.path.dirname(os.path.realpath(__file__)), "templates", subpath
    )


def get_render_dest_path(
    dest_path: str, dest_subpath: str, render_file: str
) -> str:
    """Get the destination path for the render file.

    :param dest_path: Parent path where rendered file will be stored.
    :param dest_subpath: Subpath where rendered file will be stored.
    :param render_file: File name of render file.
    """
    render_dest = os.path.join(dest_path, dest_subpath)
    os.makedirs(render_dest, exist_ok=True)
    return os.path.join(render_dest, render_file)


def render_file(
    search_path: str,
    template_name: str,
    render_data: dict[str, object],
    out_file: str,
):
    """Render a jinja2 template and data out to a file.

    :param search_path: Directory that contains the templates.
    :param template_name: Name of template file.
    :param render_data: Dictionary of data to render.
    :param out_file: Rendered output file.
    """
    loader = jinja2.FileSystemLoader(searchpath=search_path)
    jenv = jinja2.Environment(loader=loader)
    template = jenv.get_template(template_name)
    out_data = template.render(render_data=render_data)
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(out_data)
