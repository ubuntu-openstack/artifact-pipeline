# Artifact Pipeline

Automation tools and Temporal workflows for building debian packages.

## Dependencies

* Juju >= 3.1
* MicroK8s in strict confinement (e.g `1.27-strict/stable` channel)
* Charmed Temporal

## Temporal on MicroK8s

### Configure environment varaibles on MicroK8s host
Update /etc/environment on MicroK8s host with [proxy environment variables](https://MicroK8s.io/docs/install-proxy) with:
```
HTTPS_PROXY=http://squid.internal:3128
HTTP_PROXY=http://squid.internal:3128
NO_PROXY=10.0.0.0/8,192.168.0.0/16,127.0.0.1,172.16.0.0/16
https_proxy=http://squid.internal:3128
http_proxy=http://squid.internal:3128
no_proxy=10.0.0.0/8,192.168.0.0/16,127.0.0.1,172.16.0.0/16
```

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

## Backport a Package to the Cloud Archive

Install apt dependencies on worker:
```
sudo apt install --yes dput
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

[connection]
host="10.1.65.74"
port=7233
EOF
```

Run worker in a terminal:
```
artifact-pipeline.worker-archive-backport --config-file /etc/artifact-pipeline.conf
```

Run workflow in another terminal:
```
artifact-pipeline.workflow-archive-backport --config-file /etc/artifact-pipeline.conf --package python-aodhclient --os-series yoga
```

## Useful Commands
Terminate a workflow:
```
juju run temporal-admin-k8s/0 tctl args='workflow terminate --workflow_id bom-yoga-workflow'
```

