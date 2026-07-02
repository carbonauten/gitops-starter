#!/bin/sh
set -eu

PORT="${PORT:-8080}"
export PORT

mkdir -p /tmp/client_temp /tmp/proxy_temp /tmp/fastcgi_temp /tmp/uwsgi_temp /tmp/scgi_temp

envsubst '${PORT}' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf

python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --timeout-keep-alive 75 &

exec nginx -g 'daemon off;'
