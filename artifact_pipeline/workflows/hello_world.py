import argparse
import asyncio
import sys

from datetime import timedelta

from temporalio.client import Client
from temporalio import workflow

import artifact_pipeline.conf

# Import activity, passing it through the sandbox without reloading the module
with workflow.unsafe.imports_passed_through():
    from oslo_log import log as logging
    from artifact_pipeline import config
    from artifact_pipeline.activities.hello_world import say_hello


CONF = artifact_pipeline.conf.CONF
LOG = logging.getLogger(__name__)
TASK_QUEUE = "hello-task-queue"


@workflow.defn
class SayHello:
    @workflow.run
    async def run(self, name: str) -> str:
        return await workflow.execute_activity(
            say_hello, name, start_to_close_timeout=timedelta(seconds=5)
        )


def setup_opts(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('--name')
    return parser.parse_known_args()


async def async_main(argv=None):
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


def main(argv=None):
    return asyncio.run(async_main())
