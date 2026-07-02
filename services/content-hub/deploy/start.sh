#!/bin/sh
set -eu

PORT="${PORT:-8080}"
export PORT

mkdir -p /tmp/client_temp /tmp/proxy_temp /tmp/fastcgi_temp /tmp/uwsgi_temp /tmp/scgi_temp

envsubst '${PORT}' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf
nginx -t

(
  while true; do
    echo "Starting uvicorn..." >&2
    python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --timeout-keep-alive 75 || true
    echo "uvicorn exited, restarting in 2s..." >&2
    sleep 2
  done
) &

exec nginx -g 'daemon off;'
