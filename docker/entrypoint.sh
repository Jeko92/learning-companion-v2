#!/bin/sh
# Container start (see Dockerfile): apply migrations to the database on the
# data volume, then replace this shell with the command (gunicorn by default),
# so it runs as PID 1 and receives docker stop's SIGTERM.
# Without SECRET_KEY or OPENAI_API_KEY, migrate fails and names the variable.
set -eu
python src/manage.py migrate --noinput
exec "$@"
