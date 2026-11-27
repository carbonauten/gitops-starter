#!/bin/sh
# Decodes the base64-encoded signing certificate (see Dockerfile/README.md
# for why this is an env var rather than a mounted file) before starting
# Documenso's own start.sh.
set -e

if [ -n "$DOCUMENSO_CERT_P12_BASE64" ]; then
  CERT_PATH="${NEXT_PRIVATE_SIGNING_LOCAL_FILE_PATH:-/tmp/cert.p12}"
  echo "$DOCUMENSO_CERT_P12_BASE64" | base64 -d > "$CERT_PATH"
fi

exec sh start.sh
