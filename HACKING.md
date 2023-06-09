# hacking


## Prerequisite

* Juju is bootstrapped with microk8s (see [How to use microk8s with juju](https://juju.is/docs/olm/microk8s))
* tox

## Running functional tests

```
tox -e func
```

## Running a Temporal development server

Run the script `run-dev-server.sh` located at the top level of the git repository.

```
./run-dev-server.sh
```

The script downloads the `temporal` binary and runs it in development mode. The
Web UI is accessible at [http://localhost:8233/](http://localhost:8233/).
