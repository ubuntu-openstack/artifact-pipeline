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
"""Configuration for deb packaging tools."""

from oslo_config import cfg


deb_group = cfg.OptGroup(
    'deb',
    title='Deb packaging options',
    help="""Options under this group are used to define the configuration
            options related to deb packaging.""",
)

opts = [
    cfg.StrOpt(
        "DEBEMAIL",
        default="artifact-pipeline@example.com",
        help="Email address used when creating entries in debian/changelog.",
    ),
    cfg.StrOpt(
        "DEBFULLNAME",
        default="Backport O-Matic",
        help="Full name used when creating entries in debian/changelog.",
    ),
    cfg.StrOpt(
        "DEB_BUILD_OPTIONS",
        default="nostrip",
        help="deb build options",
    ),
]


def register_opts(conf: cfg.CONF):
    """Register configuration options.

    :param conf: configuration option manager.
    """
    conf.register_group(deb_group)
    conf.register_opts(opts, group=deb_group)
