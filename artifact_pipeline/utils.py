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
from collections import OrderedDict
import datetime
from glob import glob
import jinja2
import os
import subprocess

from launchpadlib.launchpad import Launchpad
from temporalio import activity
from typing import (
    Optional,
)


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
        self, cmd: str, retcode: int, output: str, work_dir: str
    ):
        """Update the build results for a package build.

        :param cmd: Most recent command that was executed.
        :param retcode: Return code from command that was executed.
        :param output: Output from command that was executed.
        :param work_dir: Directory where package build artifacts are stored.
        """
        if not self.version:
            pkg_build_dir = glob(f"{work_dir}/{self.package}*")
            if pkg_build_dir:
                self.version = pkg_build_dir[0].split(
                    f"{work_dir}/{self.package}-"
                )[1]

        if retcode:
            self.status = "failed"

        formatted = f"+ {' '.join(cmd)}\n{output}+ return code: {retcode}\n"
        if not self.output:
            self.output = formatted
        else:
            self.output = f"{self.output}\n{formatted}"

        self.logfile = f"{self.package}-{self.version}.build"

    def write_build_result(self, log_dir: str) -> str:
        """Write the build results output to a file.

        :param log_dir: Directory to store build log file in.
        """
        logfile_path = os.path.join(log_dir, self.logfile)
        with open(logfile_path, "w") as f:
            f.write(self.output)
            self.output = ""
        return logfile_path


def _render_file(
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


def _get_template_path(subpath: str = "") -> str:
    """Get full path to templates directory or templates subdirectory.

    :param subpath: Optional subdirectory.
    """
    return os.path.join(
        os.path.dirname(os.path.realpath(__file__)), "templates", subpath
    )


def _get_render_dest_path(
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


def render_css(dest_path: str):
    """Render the css files.

    :param dest_path: Parent path where rendered file will be stored.
    """
    css_files = ["filter.css", "starter-template.css", "tracker.css"]
    for css_file in css_files:
        _render_file(
            _get_template_path("css"),
            css_file,
            {},
            _get_render_dest_path(dest_path, "css", css_file),
        )


def render_js(dest_path):
    """Render the js file.

    :param dest_path: Parent path where rendered file will be stored.
    """
    js_file = "filter.js"
    _render_file(
        _get_template_path("js"),
        js_file,
        {},
        _get_render_dest_path(dest_path, "js", js_file),
    )


def render_html(
    dest_path: str,
    os_series: str,
    os_supported: list[str],
    build_results: dict[str, object],
):
    """Render html file for backport-o-matic report.

    :param dest_path: Parent path where rendered file will be stored.
    :param os_series: OpenStack series name.
    :param os_supported: List of supported OpenStack releases for navigation.
    """
    render_data = {
        "os_series": os_series,
        "timestamp": datetime.datetime.utcnow(),
        "build_results": build_results,
    }
    render_data["os_series"] = "OpenStack {}{}".format(
        os_series[0].capitalize(), os_series[1:]
    )

    href_map = OrderedDict()
    out_index_file = _get_render_dest_path(dest_path, "", "index.html")

    hrefs = [f"{rel}-builds.html" for rel in os_supported]
    hrefs.sort()
    for href in hrefs:
        raw_name = href.split("-", 1)[0]
        name = "{}{}".format(raw_name[0].capitalize(), raw_name[1:])
        href_map[name] = {}
        href_map[name]["href"] = href
        href_map[name]["status"] = "active"
    render_data["href_map"] = href_map

    out_builds_file = _get_render_dest_path(
        dest_path, "", "{}-builds.html".format(os_series)
    )

    _render_file(
        _get_template_path(), "builds.html.j2", render_data, out_builds_file
    )
    _render_file(
        _get_template_path(), "index.html.j2", render_data, out_index_file
    )


def subprocess_run(
    cmd: str, cwd: str = ".", env: dict[str, str] = {}
) -> tuple[int, str]:
    """Run command with subprocess.run.

    :param cmd: Command to run.
    :param cwd: Directory to run command in.
    :param env: Dictionary of environment variables.
    """
    activity.logger.info(f"Running command: {cmd}")
    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=cwd, env=env
    )
    activity.logger.info(f"Command output: {result.stdout.decode()}")
    return result.returncode, result.stdout.decode()


async def asyncio_create_subprocess_exec(
    cmd: str, env: dict[str, str] = {}
) -> tuple[Optional[int], str]:
    """Run command with asyncio.create_subprocess_exec.

    :param cmd: Command to run.
    :param env: Dictionary of environment variables.
    """
    activity.logger.info(f"Running command: {cmd}")
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env=env,
    )
    stdout, _ = await process.communicate()
    activity.logger.info(f"Command output: {stdout.decode()}")
    return (process.returncode, stdout.decode())


def query_ca_ppa(
    ppa_name: str, ubuntu_series: str
) -> dict[str, dict[str, str]]:
    """Get mapping of cloud-archive package names to (version, state).

    :param ppa_name: PPA name.
    :param ubuntu_series: Ubuntu series name.
    """
    activity.logger.info("Initializing connection to Lanchpad")
    conn = {}
    conn["lp"] = Launchpad.login_anonymously("openstack", "production")
    conn["ubuntu"] = conn["lp"].distributions["ubuntu"]

    # ppa = conn['lp'].people['ubuntu-cloud-archive'].getPPAByName(name=ppa)
    ppa = conn["lp"].people["corey.bryant"].getPPAByName(name=ppa_name)
    distro = ppa.distribution.getSeries(name_or_version=ubuntu_series)
    package_map = dict[str, dict[str, str]] = {}
    for pkg in ppa.getPublishedSources(
        distro_series=distro, status="Published"
    ):
        state = "current"
        if len(pkg.getPublishedBinaries()) == 0:
            # There are no published binaries, something is wrong with the
            # build. maybe dep wait, ftbfs.
            _st = " ".join(list(set([b.buildstate for b in pkg.getBuilds()])))
            if "Failed to build" in _st:
                for log in [b.build_log_url for b in pkg.getBuilds()]:
                    _st += ' <a href="{}">BL</a>'.format(log)
            state = _st

        package_map[pkg.source_package_name] = {}
        package_map[pkg.source_package_name]["original_version"] = (
            pkg.source_package_version,
            state,
        )
    return package_map


def os_auth_env(novarc: str) -> dict[str, str]:
    """Translate openstack credentials file to environment variables.

    :param novarc: OpenStack credentials file name.
    """
    env = {}
    with open(novarc, "r") as f:
        for line in f.readlines():
            line = line.replace("export ", "")
            line = line.replace('"', "")
            line = line.rstrip()
            var = line.split("=")[0]
            val = line.split("=")[1]
            env[var] = val
    return env


def swift_publish(novarc: str, path: str, header: str = "") -> int:
    """Publish to swift.

    :param novarc: OpenStack credentials file name.
    :param path: Path to publish to swift.
    :param header: Header type to publish with.
    """
    assert os.path.isfile(novarc)
    env = os_auth_env(novarc)

    activity.logger.info("Publishing to swift")
    cmds = []
    if header:
        cmds.append(
            [
                "swift",
                "upload",
                "reports",
                "--object-name",
                "backport-o-matic",
                "--header",
                f"{header}",
                path,
            ]
        )
    else:
        cmds.append(
            [
                "swift",
                "upload",
                "reports",
                "--object-name",
                "backport-o-matic",
                path,
            ]
        )
    cmds.append(["swift", "post", "--read-acl", ".r:*,.rlistings", "reports"])
    for cmd in cmds:
        retcode, output = subprocess_run(cmd, env=env)
        if retcode:
            activity.logger.error("Failure publishing to swift")
            return retcode
    return retcode


def swift_delete(novarc: str, swift_object: str) -> int:
    """Delete a swift object.

    :param novarc: OpenStack credentials file name.
    :param swift_object: Name of swift object to delete.
    """
    assert os.path.isfile(novarc)
    env = os_auth_env(novarc)

    cmd = [
        "swift",
        "delete",
        "reports",
        os.path.join("backport-o-matic", swift_object),
    ]
    retcode, output = subprocess_run(cmd, env=env)
    return retcode
