import os
import subprocess
import tempfile

import zaza.model

from zaza.charm_lifecycle import utils as lifecycle_utils


def configure_tls():
    with tempfile.mkdtemp() as tmpdir:
        server_key = os.path.join(tmpdir, 'server.key')
        server_csr = os.path.join(tmpdir, 'server.csr')
        server_crt = os.path.join(tmpdir, 'server.crt')
        # Generate private key
        subprocess.check_call(['openssl', 'genrsa', '-out', server_key,
                               '2048'])
        # Generate a certificate signing request
        subprocess.check_call(['openssl', 'req', '-new', server_key,
                               '-out', server_csr,
                               '-subj', '/CN=temporal-k8s'])
        # Create self-signed certificate
        p = subprocess.Popen(['openssl', 'x509', '-req', '-days', '365',
                              '-in', server_csr, '-signkey', server_key,
                              '-out', server_crt],
                             stdin=subprocess.PIPE, text=True)
        p.communicate("subjectAltName=DNS:temporal-k8s")
        p.wait()
        assert p.returncode == 0, str(p)

        subprocess.check_call(['microk8s.kubectl', 'create', 'secret', 'tls',
                               'temporal-tls', '--cert', server_crt,
                               '--key', server_key])
        subprocess.check_call(
            ['microk8s', 'enable',
             'ingress:default-ssl-certificate=temporal/temporal-tls']
        )

        zaza.model.wait_for_agent_status()
    test_config = lifecycle_utils.get_charm_config(fatal=False)
    target_deploy_status = test_config.get('target_deploy_status', {})
    try:
        opts = {
            'workload-status-message-prefix': '',
            'workload-status': 'active',
        }
        target_deploy_status['temporal-ui-k8s'].update(opts)
    except KeyError:
        pass

    zaza.model.wait_for_application_states(
        states=target_deploy_status)
