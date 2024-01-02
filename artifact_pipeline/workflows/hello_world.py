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
"""Logic for the hello-world workflow."""
import argparse
import asyncio
import logging
import sys
from datetime import timedelta
from typing import (
    List,
    Optional,
)

from temporalio.client import Client
from temporalio import workflow

import artifact_pipeline.conf

# Import activity, passing it through the sandbox without reloading the module
with workflow.unsafe.imports_passed_through():
    from artifact_pipeline import config
    from artifact_pipeline.activities.hello_world import say_hello


CONF = artifact_pipeline.conf.CONF
LOG = logging.getLogger(__name__)
TASK_QUEUE = "hello-task-queue"


@workflow.defn
class SayHello:
    """Workflow definition."""

    @workflow.run
    async def run(self, name: str) -> str:
        """Entry point when running this workflow.

        :param name: Name to say hello to.
        :returns: the formatted message returned by the worker.
        """
        return await workflow.execute_activity(
            say_hello, name, start_to_close_timeout=timedelta(seconds=5)
        )


def setup_opts(argv: Optional[List[str]]):
    """Parse CLI arguments.

    :param argv: list of arguments to parse
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True, help="Name to say hello to.")
    return parser.parse_known_args(argv)


async def async_main(argv: Optional[List[str]] = None):
    """Async entry point for the hello world workflow.

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
    result = await client.execute_workflow(
        SayHello.run, options.name, id="hello-workflow", task_queue=TASK_QUEUE
    )

    print(f"Result: {result}")


def main(argv: Optional[List[str]] = None):
    """Entry point for the hello world workflow.

    :param argv: list of CLI arguments.
    """
    return asyncio.run(async_main())
