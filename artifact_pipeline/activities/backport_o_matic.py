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
"""Logic for the backport-o-matic related activities."""
import datetime
import pickle
from collections import OrderedDict
from typing import Optional

from launchpadlib.launchpad import Launchpad  # type: ignore
from temporalio import activity

from artifact_pipeline import utils


@activity.defn
async def get_outdated_packages(
    os_series: str,
) -> tuple[list[str], Optional[int], str]:
    """Get outdated cloud-archive packages.

    :param os_series: OpenStack series name.
    """
    cmd = ["cloud-archive-outdated-packages", "--proposed", os_series]
    returncode, output = await utils.asyncio_create_subprocess_exec(
        cmd,
        redirect_stderr=False,
    )

    return (cmd, returncode, output)


@activity.defn
async def get_staging_packages(
    os_series: str,
) -> dict[str, dict[str, tuple]]:
    """Get mapping of cloud-archive package names to (version, state).

    :param os_series: OpenStack series name.
    """
    activity.logger.info("Initializing connection to Lanchpad")
    conn = {}
    conn["lp"] = Launchpad.login_anonymously("openstack", "production")
    conn["ubuntu"] = conn["lp"].distributions["ubuntu"]

    ppa_name = f"{os_series}-staging"
    ppa = conn["lp"].people["ubuntu-cloud-archive"].getPPAByName(name=ppa_name)
    ubuntu_series = utils.OS_SERIES_BACKPORTING[os_series]
    distro = ppa.distribution.getSeries(name_or_version=ubuntu_series)
    package_map: dict[str, dict[str, tuple]] = {}
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


@activity.defn
async def render_css(www_dir: str):
    """Render the css files.

    :param www_dir: Parent directory where rendered file will be stored.
    """
    css_files = ["filter.css", "starter-template.css", "tracker.css"]
    for css_file in css_files:
        utils.render_file(
            utils.get_template_path("css"),
            css_file,
            {},
            utils.get_render_dest_path(www_dir, "css", css_file),
        )


@activity.defn
async def render_js(www_dir):
    """Render the js file.

    :param www_dir: Parent directory where rendered file will be stored.
    """
    js_file = "filter.js"
    utils.render_file(
        utils.get_template_path("js"),
        js_file,
        {},
        utils.get_render_dest_path(www_dir, "js", js_file),
    )


@activity.defn
async def render_html(
    www_dir: str,
    os_series: str,
    os_supported: list[str],
    build_results_pickled: bytes,
):
    """Render html file for backport-o-matic report.

    :param www_dir: Parent directory where rendered file will be stored.
    :param os_series: OpenStack series name.
    :param os_supported: List of supported OpenStack releases for navigation.
    """
    build_results = pickle.loads(build_results_pickled)
    render_data = {
        "os_series": os_series,
        "timestamp": datetime.datetime.utcnow(),
        "build_results": build_results,
    }
    render_data["os_series"] = "OpenStack {}{}".format(
        os_series[0].capitalize(), os_series[1:]
    )

    href_map: dict[str, dict[str, str]] = OrderedDict()
    out_index_file = utils.get_render_dest_path(www_dir, "", "index.html")

    hrefs = [f"{rel}-builds.html" for rel in os_supported]
    hrefs.sort()
    for href in hrefs:
        raw_name = href.split("-", 1)[0]
        name = "{}{}".format(raw_name[0].capitalize(), raw_name[1:])
        href_map[name] = {}
        href_map[name]["href"] = href
        href_map[name]["status"] = "active"
    render_data["href_map"] = href_map

    out_builds_file = utils.get_render_dest_path(
        www_dir, "", "{}-builds.html".format(os_series)
    )

    utils.render_file(
        utils.get_template_path(),
        "builds.html.j2",
        render_data,
        out_builds_file,
    )
    utils.render_file(
        utils.get_template_path(), "index.html.j2", render_data, out_index_file
    )


@activity.defn
async def swift_publish(
        novarc: str, path: str, header: str = ""
) -> Optional[int]:
    """Publish to swift.

    :param novarc: OpenStack credentials file name.
    :param path: Path to publish to swift.
    :param header: Header type to publish with.
    """
    returncode: Optional[int] = 0
    env = utils.os_auth_env(novarc)

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
        returncode, output = await utils.asyncio_create_subprocess_exec(
            cmd,
            env=env,
        )
        if returncode:
            activity.logger.error("Failure publishing to swift")
            return returncode
    return returncode
