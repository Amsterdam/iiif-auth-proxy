#!/usr/bin/env bash

set -u  # crash on missing env variables
set -e  # stop on any error
set -x  # print what we are doing

# Write cert file from env var
echo -e "$IIIF_IMAGE_SERVER_WABO_CERT" | base64 --decode  > /tmp/sw444v1912.pem

# run uwsgi
cd /src
exec uwsgi
