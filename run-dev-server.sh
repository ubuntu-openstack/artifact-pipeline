#!/bin/bash -eux

test -f temporal || wget "https://temporal.download/cli/archive/latest?platform=linux&arch=amd64" -O - | tar xzf - temporal
chmod +x temporal
./temporal server start-dev
