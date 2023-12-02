from oslo_config import cfg  # type: ignore

from artifact_pipeline.conf import connection
from artifact_pipeline.conf import deb


CONF = cfg.CONF

connection.register_opts(CONF)
deb.register_opts(CONF)
