from oslo_config import cfg

from artifact_pipeline.conf import connection

CONF = cfg.CONF

connection.register_opts(CONF)
