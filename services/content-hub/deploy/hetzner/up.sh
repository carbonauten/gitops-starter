#!/usr/bin/env bash
# Run on the Hetzner server after .env is configured.
set -euo pipefail

cd "$(dirname "$0")/../.."

docker compose pull
docker compose up -d
docker compose ps
