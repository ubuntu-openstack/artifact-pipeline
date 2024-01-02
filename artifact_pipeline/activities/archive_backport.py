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
"""Logic for the archive-backport related activities."""
from glob import glob
import os
import pathlib

from typing import (
    Union,
)
from temporalio import activity

import artifact_pipeline.conf
from artifact_pipeline import utils

CONF = artifact_pipeline.conf.CONF


@activity.defn
async def prepare_package(
    package_name: str,
    os_series: str,
    suffix: str,
    work_dir: Union[str, pathlib.Path],
    check_proposed: bool = True,
) -> tuple[list[str], int, str]:
    """Backport a package (by name) from the Ubuntu archive to UCA.

    :param package_name: Name of the package to backport.
    :param os_series: OpenStack series name.
    :param suffix: Package version suffix (ie. ~cloud0).
    :param work_dir: Directory where package build artifacts are stored.
    :param check_proposed: If true consider packages in the proposed pocket.
    """
    activity.logger.info(f"Work directory: {work_dir}")
    if not os.path.isdir(work_dir):
        activity.logger.info("Work directory does not exist, creating it.")
        os.mkdir(work_dir)

    cmd = [
        "cloud-archive-backport",
        "--suffix",
        f"{suffix}",
        "--yes",
        "--release",
        os_series,
        "--outdir",
        str(work_dir),
        package_name,
    ]
    if check_proposed:
        cmd.append("--proposed")
    cmd.append(package_name)

    env = {"DEBEMAIL": CONF.deb.DEBEMAIL, "DEBFULLNAME": CONF.deb.DEBFULLNAME}

    returncode, output = await utils.asyncio_create_subprocess_exec(cmd, env)

    return (cmd, returncode, output)


@activity.defn
async def build_package(
    package_name: str, os_series: str, work_dir: Union[str, pathlib.Path]
) -> tuple[list[str], int, str]:
    """Backport a package (by name) from the Ubuntu archive to UCA.

    :param package_name: Name of the package to build.
    :param os_series: OpenStack series name.
    :param work_dir: Directory where package build artifacts are stored.
    """
    dsc_file = glob(
        os.path.join(work_dir, f"{package_name}*", f"{package_name}_*.dsc")
    )
    cmd = [f"sbuild-{os_series}", "--nolog", "--arch-all", dsc_file[0]]

    env = {
        "DEBEMAIL": CONF.deb.DEBEMAIL,
        "DEBFULLNAME": CONF.deb.DEBFULLNAME,
        "DEB_BUILD_OPTIONS": CONF.deb.DEB_BUILD_OPTIONS,
    }

    returncode, output = await utils.asyncio_create_subprocess_exec(cmd, env)

    return (cmd, returncode, output)


@activity.defn
async def sign_package(
    package_name, work_dir: Union[str, pathlib.Path]
) -> tuple[list[str], int, str]:
    """Sign a package changes file.

    :param package_name: Name of the package.
    :param work_dir: Directory where package build artifacts are stored.
    """
    changes_file = glob(
        os.path.join(
            work_dir, f"{package_name}*", f"{package_name}_*_source.changes"
        )
    )
    signing_key = CONF.deb.signing_key
    cmd = ["debsign", f"-k{signing_key}", changes_file[0]]
    returncode, output = await utils.asyncio_create_subprocess_exec(cmd)

    return (cmd, returncode, output)


@activity.defn
async def upload_package(
    package_name: str, os_series: str, work_dir: Union[str, pathlib.Path]
) -> tuple[list[str], int, str]:
    """Sign a package changes file.

    :param package_name: Name of the package.
    :param os_series: OpenStack series name.
    :param work_dir: Directory where package build artifacts are stored.
    """
    staging_ppa = f"ppa:ubuntu-cloud-archive/{os_series}-staging"
    changes_file = glob(
        os.path.join(
            work_dir, f"{package_name}*", f"{package_name}_*_source.changes"
        )
    )
    cmd = ["dput", "--force", staging_ppa, changes_file[0]]
    returncode, output = await utils.asyncio_create_subprocess_exec(cmd)

    return (cmd, returncode, output)
