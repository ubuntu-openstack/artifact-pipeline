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
"""Logic for the hello-world worker daemon."""
import asyncio
import sys

from typing import (
    List,
    Optional,
)

from temporalio import workflow
from temporalio.client import Client
from temporalio.worker import Worker

import artifact_pipeline.conf

from artifact_pipeline.activities.archive_backport import (
    cloud_archive_backport,
    sbuild_package,
)
from artifact_pipeline.workflows import archive_backport

# Import activity, passing it through the sandbox without reloading the module
with workflow.unsafe.imports_passed_through():
    from oslo_log import log as logging
    from artifact_pipeline import config


CONF = artifact_pipeline.conf.CONF
LOG = logging.getLogger(__name__)


async def async_main(argv: Optional[List[str]] = None):
    """Async entry point for the archive backport worker.

    :param argv: list of CLI arguments.
    """
    if argv is None:
        argv = sys.argv

    config.parse_args(argv)
    logging.setup(CONF, "artifact-pipeline")
    client = await Client.connect(
        "%s:%d" % (CONF.connection.host, CONF.connection.port),
        namespace=CONF.connection.namespace,
    )

    # Run the worker
    worker = Worker(
        client,
        task_queue=archive_backport.TASK_QUEUE,
        workflows=[archive_backport.ArchiveBackport],
        activities=[cloud_archive_backport,
                    sbuild_package]
    )
    await worker.run()


def main(argv: Optional[List[str]] = None):
    """Entry point for the hello world worker.

    :param argv: list of CLI arguments.
    """
    return asyncio.run(async_main(argv))
