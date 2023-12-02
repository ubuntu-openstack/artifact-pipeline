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
import pickle
import sys
from collections import OrderedDict
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
    from artifact_pipeline.activities import backport_o_matic


CONF = artifact_pipeline.conf.CONF
TASK_QUEUE = "backport-o-matic"


@workflow.defn(sandboxed=False)
class BackportOMatic:
    """Workflow to describe a backport from the Ubuntu archive into a PPA."""

    @workflow.run
    async def run(
        self,
        os_series: str,
        exclude_list: list[str],
        novarc: str,
        work_dir: str,
        www_dir: str,
        build_log_dir: str,
    ) -> str:
        """Start the backporting process.

        :param os_series: OpenStack series name.
        :param exclude_list: List of packages to exclude from backporting.
        :param novarc: OpenStack credentials file name.
        :param work_dir: Directory to store package build artifacts.
        :param www_dir: Directory to store website files prior to swift upload.
        :param build_log_dir: Directory to store logs prior to swift upload.
        """
        build_results = OrderedDict()

        overall_result = "Success"

        staging_packages = await workflow.execute_activity(
            backport_o_matic.get_staging_packages,
            args=[os_series],
            start_to_close_timeout=timedelta(seconds=3600),
        )

        for package_name in staging_packages.keys():
            version = staging_packages[package_name]["original_version"][0]
            status = staging_packages[package_name]["original_version"][1]

            build = utils.BuildResult(package_name, version, status)
            build.update_build_result(
                cmd=[],
                retcode=0,
                output="",
                work_dir=work_dir,
            )
            build.write_build_result(build_log_dir)
            build_results[package_name] = build

        (cmd, retcode, output) = await workflow.execute_activity(
            backport_o_matic.get_outdated_packages,
            args=[os_series],
            start_to_close_timeout=timedelta(seconds=3600),
        )
        if retcode:
            raise RuntimeError("get_outdated_packages failed: {output}")
        packages = [p for p in output.strip().split(" ") if p]

        for package_name in packages:
            if exclude_list and package_name in exclude_list:
                workflow.logger.info(f"Excluding {package_name} from backport")
                continue

            build = utils.BuildResult(package_name)

            (cmd, retcode, output) = await workflow.execute_activity(
                backport_package.prepare_package,
                args=[package_name, os_series, "~cloud0", work_dir, True],
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

            if retcode:
                overall_result = "Failed"

            build.write_build_result(build_log_dir)
            build_results[package_name] = build

        await workflow.execute_activity(
            backport_o_matic.render_css,
            args=[www_dir],
            start_to_close_timeout=timedelta(seconds=3600),
        )

        await workflow.execute_activity(
            backport_o_matic.render_js,
            args=[www_dir],
            start_to_close_timeout=timedelta(seconds=3600),
        )

        await workflow.execute_activity(
            backport_o_matic.render_html,
            args=[
                www_dir,
                os_series,
                list(utils.OS_SERIES_BACKPORTING.keys()),
                pickle.dumps(build_results),
            ],
            start_to_close_timeout=timedelta(seconds=3600),
        )

        await workflow.execute_activity(
            backport_o_matic.swift_publish,
            args=[novarc, www_dir],
            start_to_close_timeout=timedelta(seconds=3600),
        )

        await workflow.execute_activity(
            backport_o_matic.swift_publish,
            args=[novarc, build_log_dir, "content-type:text/plain"],
            start_to_close_timeout=timedelta(seconds=3600),
        )

        return overall_result


def setup_opts(argv: Optional[list[str]]):
    """Parse CLI arguments.

    :param argv: list of arguments to parse
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--os-series",
        required=True,
        help="Cloud Archive OpenStack release to backport to.",
    )
    parser.add_argument(
        "-e",
        "--exclude-list",
        dest="exclude_list",
        nargs="+",
        default=[],
        help="Packages to exclude from backporting.",
    )
    parser.add_argument(
        "-n",
        "--novarc",
        dest="novarc",
        default="/home/ubuntu/novarc",
        help="OpenStack credentials file name used for uploading to swift.",
    )
    parser.add_argument(
        "-w",
        "--work-dir",
        dest="work_dir",
        default="./work-dir",
        help="Directory to store package build artifacts.",
    )
    parser.add_argument(
        "-s",
        "--site-dir",
        dest="site_dir",
        default="./site-dir",
        help="Directory to store website files prior to swift upload.",
    )
    return parser.parse_known_args(argv)


async def async_main(argv: Optional[list[str]] = None):
    """Async entry point for the backport-o-matic workflow.

    :param argv: list of CLI arguments.
    """
    if argv is None:
        argv = sys.argv

    (options, args) = setup_opts(argv)
    config.parse_args(args)

    if options.os_series not in utils.OS_SERIES_BACKPORTING.keys():
        raise RuntimeError("Value specified for --os-series is not valid")

    if not os.path.isfile(options.novarc):
        raise RuntimeError("{novarc} file does not exist")

    client = await Client.connect(
        f"{CONF.connection.host}:{CONF.connection.port}",
        namespace=CONF.connection.namespace,
    )

    www_dir = os.path.join(options.site_dir, "www")
    build_log_dir = os.path.join(options.site_dir, "build-logs")
    if not os.path.isdir(options.work_dir):
        os.mkdir(options.work_dir)
    if not os.path.isdir(options.site_dir):
        os.mkdir(options.site_dir)
    if not os.path.isdir(www_dir):
        os.mkdir(www_dir)
    if not os.path.isdir(build_log_dir):
        os.mkdir(build_log_dir)

    workflow_id = f"backport-o-matic-{options.os_series}"
    result = await client.execute_workflow(
        BackportOMatic.run,
        args=[
            options.os_series,
            options.exclude_list,
            options.novarc,
            options.work_dir,
            www_dir,
            build_log_dir,
        ],
        id=workflow_id,
        task_queue=TASK_QUEUE,
        cron_schedule="0 * * * *",
    )
    print(f"Result: {result}")


def main(argv: Optional[list[str]] = None):
    """Entry point for the backport-o-matic workflow.

    :param argv: list of CLI arguments.
    """
    return asyncio.run(async_main())
