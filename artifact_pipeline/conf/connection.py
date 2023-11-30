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
"""Connection to the Temporal server configuration schema."""

from oslo_config import cfg


connection_group = cfg.OptGroup(
    "connection",
    title="Temporal Server Connection options",
    help="""Options under this group are used to define the connection details
            to a Temporal Server.""",
)

opts = [
    cfg.StrOpt(
        "host",
        default="localhost",
        help="Connect to the Temporal server on the given host.",
    ),
    cfg.IntOpt(
        "port",
        default=7233,
        help="The TCP/IP port number to use for the connection.",
    ),
    cfg.StrOpt(
        "namespace",
        default="default",
        help="Namespace to connect to in the Temporal server.",
    ),
]


def register_opts(conf: cfg.CONF):
    """Register configuration options.

    :param conf: configuration option manager.
    """
    conf.register_group(connection_group)
    conf.register_opts(opts, group=connection_group)
