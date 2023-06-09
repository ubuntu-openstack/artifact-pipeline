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
"""Workflow definition to backport packages."""
import argparse
import asyncio
import pathlib
import sys

from datetime import timedelta
from typing import (
    List,
    Optional,
    Tuple,
    Union
)

from temporalio.client import Client
from temporalio import workflow

import artifact_pipeline.conf

# Import activity, passing it through the sandbox without reloading the module
with workflow.unsafe.imports_passed_through():
    from oslo_log import log as logging
    from artifact_pipeline import config
    from artifact_pipeline.activities import archive_backport


CONF = artifact_pipeline.conf.CONF
LOG = logging.getLogger(__name__)
TASK_QUEUE = "archive-backport"


@workflow.defn
class ArchiveBackport:
    """Workflow to describe a backport from the Ubuntu archive into a PPA."""

    @workflow.run
    async def run(self,
                  package_name: str,
                  os_series: str,
                  dstdir: Union[str, pathlib.Path],
                  check_proposed: bool = True) -> Tuple[int, str, str]:
        """Start the backporting process.

        :param package_name: Name of the package to backport.
        :param os_series: OpenStack series name.
        :param dstdir: Path to the directory where to save the deb source
                       package.
        :param check_proposed: If true consider packages in the proposed pocket.
        """
        (returncode, stdout, stderr) =  await workflow.execute_activity(
            archive_backport.cloud_archive_backport,
            args=[package_name, os_series, dstdir, check_proposed],
            start_to_close_timeout=timedelta(seconds=3600)
        )
        if returncode != 0:
            return (returncode, stdout, stderr)
        else:
            LOG.debug('Successfully backported package')

        (returncode, stdout, stderr) =  await workflow.execute_activity(
            archive_backport.sbuild_package,
            args=[package_name, os_series, dstdir],
            start_to_close_timeout=timedelta(seconds=3600)
        )
        return (returncode, stdout, stderr)


def setup_opts(argv: Optional[List[str]]):
    """Parse CLI arguments.

    :param argv: list of arguments to parse
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--package',
                        dest='package_name',
                        required=True,
                        help="Name of the package to backport.")
    parser.add_argument('--os-series',
                        required=True,
                        help="Cloud Archive OpenStack release to backport to.")
    parser.add_argument('-d', '--dstdir', dest='dstdir', default='./',
                        help='Directory to save the source package.')
    parser.add_argument('-P', '--proposed', dest='check_proposed',
                        action='store_true', help='Check proposed pocket')
    return parser.parse_known_args(argv)


async def async_main(argv: Optional[List[str]] = None):
    """Async entry point for the archive backport workflow.

    :param argv: list of CLI arguments.
    """
    if argv is None:
        argv = sys.argv

    (options, args) = setup_opts(argv)
    config.parse_args(args)

    # Create client connected to server at the given address
    client = await Client.connect(
        "%s:%d" % (CONF.connection.host, CONF.connection.port),
        namespace=CONF.connection.namespace,
    )

    # Execute a workflow
    workflow_id = "archive-backport-{os_series}-{package}".format(
        os_series=options.os_series, package=options.package_name
    )
    result = await client.execute_workflow(
        ArchiveBackport.run,
        args=[options.package_name,
        options.os_series,
        options.dstdir,
        options.check_proposed],
        id=workflow_id,
        task_queue=TASK_QUEUE
    )

    print(f"Result: {result}")


def main(argv: Optional[List[str]] = None):
    """Entry point for the hello world workflow.

    :param argv: list of CLI arguments.
    """
    return asyncio.run(async_main())
