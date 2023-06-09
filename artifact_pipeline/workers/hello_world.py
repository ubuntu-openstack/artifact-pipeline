import asyncio
import sys

from temporalio import workflow
from temporalio.client import Client
from temporalio.worker import Worker

import artifact_pipeline.conf

from artifact_pipeline.activities.hello_world import say_hello
from artifact_pipeline.workflows.hello_world import (
    SayHello,
    TASK_QUEUE,
)

# Import activity, passing it through the sandbox without reloading the module
with workflow.unsafe.imports_passed_through():
    from oslo_log import log as logging
    from artifact_pipeline import config


CONF = artifact_pipeline.conf.CONF
LOG = logging.getLogger(__name__)


async def async_main(argv=None):
    if argv is None:
        argv = sys.argv

    config.parse_args(argv)
    client = await Client.connect(
        "%s:%d" % (CONF.connection.host, CONF.connection.port),
        namespace=CONF.connection.namespace,
    )

    # Run the worker
    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[SayHello],
        activities=[say_hello]
    )
    await worker.run()


def main(argv=None):
    return asyncio.run(async_main(argv))
