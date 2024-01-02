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
import os
import sys
from datetime import timedelta
from typing import Optional

from temporalio.client import Client
from temporalio import workflow

import artifact_pipeline.conf
from artifact_pipeline import utils

# Import activity, passing it through the sandbox without reloading the module
with workflow.unsafe.imports_passed_through():
    from artifact_pipeline import config
    from artifact_pipeline.activities import backport_package


CONF = artifact_pipeline.conf.CONF
TASK_QUEUE = "backport-package"


@workflow.defn(sandboxed=False)
class BackportPackage:
    """Workflow to describe a backport from the Ubuntu archive into a PPA."""

    @workflow.run
    async def run(
        self,
        package_name: str,
        os_series: str,
        suffix: str,
        work_dir: str,
        check_proposed: bool = True,
    ) -> tuple[int, str]:
        """Start the backporting process.

        :param package_name: Name of the package to backport.
        :param os_series: OpenStack series name.
        :param suffix: Package version suffix (ie. ~cloud0).
        :param work_dir: Path to directory to store package build artifacts.
        :param check_proposed: If true, consider packages from proposed pocket.
        """
        build = utils.BuildResult(package_name)

        (cmd, retcode, output) = await workflow.execute_activity(
            backport_package.prepare_package,
            args=[package_name, os_series, suffix, work_dir, check_proposed],
            start_to_close_timeout=timedelta(seconds=3600),
        )
        build.update_build_result(cmd, retcode, output, work_dir)

        if not retcode:
            (cmd, retcode, output) = await workflow.execute_activity(
                backport_package.build_package,
                args=[package_name, os_series, work_dir],
                start_to_close_timeout=timedelta(seconds=3600),
            )
            build.update_build_result(cmd, retcode, output, work_dir)

        if not retcode:
            (cmd, retcode, output) = await workflow.execute_activity(
                backport_package.sign_package,
                args=[package_name, work_dir],
                start_to_close_timeout=timedelta(seconds=3600),
            )
            build.update_build_result(cmd, retcode, output, work_dir)

        if not retcode:
            (cmd, retcode, output) = await workflow.execute_activity(
                backport_package.upload_package,
                args=[package_name, os_series, work_dir],
                start_to_close_timeout=timedelta(seconds=3600),
            )
            build.update_build_result(cmd, retcode, output, work_dir)

        log_file = build.write_build_result(work_dir)

        return (retcode, log_file)


def setup_opts(argv: Optional[list[str]]):
    """Parse CLI arguments.

    :param argv: list of arguments to parse
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--package",
        dest="package_name",
        required=True,
        help="Name of the package to backport.",
    )
    parser.add_argument(
        "--os-series",
        required=True,
        help="Cloud Archive OpenStack release to backport to.",
    )
    parser.add_argument(
        "--suffix",
        dest="suffix",
        default="~cloud0",
        help="Package version suffix.",
    )
    parser.add_argument(
        "-w",
        "--work-dir",
        dest="work_dir",
        default="./work-dir",
        help="Directory to store package build artifacts.",
    )
    parser.add_argument(
        "-p",
        "--proposed",
        dest="check_proposed",
        action="store_true",
        help="Check proposed pocket",
    )
    return parser.parse_known_args(argv)


async def async_main(argv: Optional[list[str]] = None):
    """Async entry point for the backport-package workflow.

    :param argv: list of CLI arguments.
    """
    if argv is None:
        argv = sys.argv

    (options, args) = setup_opts(argv)
    config.parse_args(args)

    if not os.path.isdir(options.work_dir):
        os.mkdir(options.work_dir)

    # Create client connected to server at the given address
    client = await Client.connect(
        f"{CONF.connection.host}:{CONF.connection.port}",
        namespace=CONF.connection.namespace,
    )

    # Execute a workflow
    workflow_id = (
        f"backport-package-{options.os_series}-{options.package_name}"
    )
    retcode, log_file = await client.execute_workflow(
        BackportPackage.run,
        args=[
            options.package_name,
            options.os_series,
            options.suffix,
            options.work_dir,
            options.check_proposed,
        ],
        id=workflow_id,
        task_queue=TASK_QUEUE,
    )

    print(f"Result: {'Failure' if retcode else 'Success'}")
    print(f"Build Log: {log_file}")


def main(argv: Optional[list[str]] = None):
    """Entry point for the backport-package workflow.

    :param argv: list of CLI arguments.
    """
    return asyncio.run(async_main())
