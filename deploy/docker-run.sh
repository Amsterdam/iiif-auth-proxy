#!/usr/bin/env bash

set -u  # crash on missing env variables
set -e  # stop on any error
set -x  # print what we are doing

# run uwsgi
cd /src
exec uwsgi --ini main/uwsgi.ini
