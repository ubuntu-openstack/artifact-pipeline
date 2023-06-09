from oslo_config import cfg


connection_group = cfg.OptGroup(
    'connection',
    title='Temporal Server Connection options',
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
        help="Namespace to connect to in the Temporal server."
    ),
]


def register_opts(conf):
    conf.register_group(connection_group)
    conf.register_opts(opts, group=connection_group)
