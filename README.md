# Artifact Pipeline

Automation tools and Temporal workflows for building debian packages.

## Dependencies

* Juju >= 3.1
* MicroK8s in strict confinement (e.g `1.27-strict/stable` channel)
* Charmed Temporal

## Temporal on MicroK8s

### Configure environment variables on MicroK8s host
Update /etc/environment on MicroK8s host with [proxy environment variables](https://MicroK8s.io/docs/install-proxy) with:
```
HTTPS_PROXY=http://squid.internal:3128
HTTP_PROXY=http://squid.internal:3128
NO_PROXY=10.0.0.0/8,192.168.0.0/16,127.0.0.1,172.16.0.0/16
https_proxy=http://squid.internal:3128
http_proxy=http://squid.internal:3128
no_proxy=10.0.0.0/8,192.168.0.0/16,127.0.0.1,172.16.0.0/16
```

Log out and back in after updating /etc/environment.

### Set up MicroK8s and Temporal

Follow the [temporal tutorial](https://charmhub.io/temporal-k8s/docs/t-introduction) for setting up Temporal on MicroK8s.

After MicroK8s is installed, reconfigure CoreDNS if 8.8.8.8 and 8.8.4.4 DNS servers are not reachable:
```
resolvectl
sudo microk8s disable dns
sudo microk8s enable dns:10.245.160.2
```
The forward DNS servers can also be modified after enabling the addon:
```
microk8s kubectl -n kube-system edit configmap/coredns
```
Access UI once temporal-ui-k8s is deployed:
```
juju status temporal-ui-k8s
sshuttle -r ubuntu@temporal 10.1.65.0/24 -D
```

## Setup for Backport Package Workflows

This setup is required for backport-package and backport-o-matic.

Install apt dependencies on worker:
```
sudo add-apt-repository --yes ppa:ubuntu-cloud-archive/tools
sudo apt install --yes cloud-archive-utils dput python3-swiftclient sendmail tox
```

Create sbuild chroots on worker:
```
mk-sbuild jammy
mk-sbuild focal
mk-sbuild bionic
```

Create config file:
```
cat << EOF > /etc/artifact-pipeline.conf
[deb]
DEBEMAIL="openstack-ubuntu-testing@lists.launchpad.net"
DEBFULLNAME="Openstack Ubuntu Testing Bot"
signing_key="D8761071DE48C342108B1AC000FA37C39935ACDC"

[connection]
host="10.1.65.74"
port=7233
EOF
```

Update /home/ubuntu/.gnupg/ for lp:~openstack-ubuntu-testing-bot user:
```
rsync -avrz -e ssh ./.gnupg/ temporal:/home/ubuntu/.gnupg/
```

Update /home/ubuntu/novarc with credentials for swift uploads:
```
rsync -avrz -e ssh ./novarc temporal:/home/ubuntu/novarc
```

## Backport a New Package to the Cloud Archive
Run worker in a terminal:
```
artifact-pipeline.backport-package-worker --config-file /etc/artifact-pipeline.conf
```

Run workflow in another terminal:
```
artifact-pipeline.backport-package-workflow --config-file /etc/artifact-pipeline.conf --package python-aodhclient --os-series yoga
```

This workflow will run one time and complete.

## Auto-Backport New Package Versions to the Cloud Archive
Run worker in a terminal:
```
artifact-pipeline.backport-o-matic-worker --config-file /etc/artifact-pipeline.conf
```

Run workflow in another terminal:
```
artifact-pipeline.backport-o-matic-workflow --config-file /etc/artifact-pipeline.conf --os-series caracal
```

This workflow will run forever as an hourly cron job.

Full list of workflow commands for currently active backport releases:
```
artifact-pipeline.backport-o-matic-workflow --config-file /etc/artifact-pipeline.conf --exclude-list debhelper pkgbinarymangler --os-series queens
artifact-pipeline.backport-o-matic-workflow --config-file /etc/artifact-pipeline.conf --exclude-list debhelper pkgbinarymangler meson --os-series ussuri
artifact-pipeline.backport-o-matic-workflow --config-file /etc/artifact-pipeline.conf --exclude-list python-tz --os-series yoga
artifact-pipeline.backport-o-matic-workflow --config-file /etc/artifact-pipeline.conf --os-series antelope
artifact-pipeline.backport-o-matic-workflow --config-file /etc/artifact-pipeline.conf --os-series bobcat
artifact-pipeline.backport-o-matic-workflow --config-file /etc/artifact-pipeline.conf --os-series caracal
```

## Scripts for running workers and backport-o-matic

This is useful for now, until we have a working snap or charm.

```
tox -e venv
source .tox/venv/bin/activate
cd tools
./run-backport-workers
./run-backport-workflows
```

## Useful Commands
Terminate a workflow:
```
juju run temporal-admin-k8s/0 tctl args='workflow terminate --workflow_id backport-o-matic-yoga'
```

