#!/bin/sh
set -eu

PORT="${PORT:-8080}"
export PORT

health_check() {
  python -c "
import urllib.request
import sys
try:
    urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2)
except Exception:
    sys.exit(1)
" 2>/dev/null
}

mkdir -p /tmp/client_temp /tmp/proxy_temp /tmp/fastcgi_temp /tmp/uwsgi_temp /tmp/scgi_temp

envsubst '${PORT}' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf
nginx -t

python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 &
UVICORN_PID=$!

ready=0
for _ in $(seq 1 45); do
  if health_check; then
    ready=1
    break
  fi
  if ! kill -0 "$UVICORN_PID" 2>/dev/null; then
    echo "uvicorn exited before becoming ready" >&2
    wait "$UVICORN_PID" || true
    exit 1
  fi
  sleep 2
done

if [ "$ready" -ne 1 ]; then
  echo "uvicorn did not become ready in time" >&2
  kill "$UVICORN_PID" 2>/dev/null || true
  exit 1
fi

(
  while true; do
    wait "$UVICORN_PID" || true
    echo "uvicorn exited, restarting in 2s..." >&2
    sleep 2
    python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 &
    UVICORN_PID=$!
    for _ in $(seq 1 30); do
      health_check && break
      sleep 2
    done
  done
) &

exec nginx -g 'daemon off;'
