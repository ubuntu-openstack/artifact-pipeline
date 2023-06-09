from oslo_log import log

import artifact_pipeline.conf
from artifact_pipeline import version

CONF = artifact_pipeline.conf.CONF


def parse_args(argv, default_config_files=None, configure_db=True,
               init_rpc=True):
    log.register_options(CONF)

    CONF(argv[1:],
         project='artifact-pipeline',
         version=version.version_string(),
         default_config_files=default_config_files)
