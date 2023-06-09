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
"""Logic for the hello-world related activities."""
import asyncio
import os
import pathlib

from typing import (
    Tuple,
    Union,
)
from temporalio import activity
from temporalio import workflow

import artifact_pipeline.conf


with workflow.unsafe.imports_passed_through():
    from oslo_log import log as logging


LOG = logging.getLogger(__name__)
CONF = artifact_pipeline.conf.CONF


@activity.defn
async def cloud_archive_backport(package_name: str,
                                 os_series: str,
                                 dstdir: Union[str, pathlib.Path],
                                 check_proposed: bool = True) -> Tuple[int, str, str]:
    """Backport a package (by name) from the Ubuntu archive to UCA.

    :param package_name: Name of the package to backport.
    :param os_series: OpenStack series name.
    :param dstdir: Path to the directory where to save the deb source package.
    :param check_proposed: If true consider packages in the proposed pocket.
    """
    LOG.warn('dstdir: %s, type: %s', dstdir, type(dstdir))
    if not os.path.isdir(dstdir):
        LOG.info('Destination directory does not exist, creating it.')
        os.mkdir(dstdir)

    cmd = ['cloud-archive-backport', '-y', '-r', os_series, '-o', str(dstdir)]
    if check_proposed:
        cmd.append('-P')

    cmd.append(package_name)
    LOG.warn('cmd: %s', cmd)
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={"DEBEMAIL": CONF.deb.DEBEMAIL,
             "DEBFULLNAME": CONF.deb.DEBFULLNAME},
    )
    stdout = b''
    while proc.returncode is None:
        line = await proc.stdout.readline()
        if line:
            stdout += line
            LOG.debug("%s", line.decode('utf-8'))
        if proc.stdout.at_eof():
            break

    _stdout, stderr = await proc.communicate()

    return (proc.returncode, stdout.decode('utf-8'), stderr.decode('utf-8'))


@activity.defn
async def sbuild_package(package_name: str,
                         os_series: str,
                         dstdir: Union[str, pathlib.Path]) -> Tuple[int, str, str]:
    """Backport a package (by name) from the Ubuntu archive to UCA.

    :param package_name: Name of the package to backport.
    :param os_series: OpenStack series name.
    :param dstdir: Path to the directory where to save the deb source package.
    """
    cmd = ['sbuild-%s' % os_series, '-n', '-A',
           "{package_name}*/{package_name}_*.dsc".format(package_name=package_name)]
    LOG.warn('cmd: %s', cmd)
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={"DEBEMAIL": CONF.deb.DEBEMAIL,
             "DEBFULLNAME": CONF.deb.DEBFULLNAME,
             "DEB_BUILD_OPTIONS": CONF.deb.DEB_BUILD_OPTIONS},
    )
    stdout = b''
    while proc.returncode is None:
        line = await proc.stdout.readline()
        if line:
            stdout += line
            LOG.debug("%s", line.decode('utf-8'))
        if proc.stdout.at_eof():
            break

    _stdout, stderr = await proc.communicate()

    return (proc.returncode, stdout.decode('utf-8'), stderr.decode('utf-8'))
