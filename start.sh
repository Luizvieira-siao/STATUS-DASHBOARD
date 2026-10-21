#!/usr/bin/env bash
set -o errexit
set -o nounset
set -o pipefail
python manage.py migrate --noinput
exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --access-logfile - --error-logfile -
