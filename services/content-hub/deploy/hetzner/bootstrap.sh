#!/usr/bin/env bash
# One-time bootstrap for a fresh Hetzner Ubuntu server.
# Run as root: bash bootstrap.sh

set -euo pipefail

APP_DIR="/opt/unified-carbonauten-platform"

echo "==> Installing Docker..."
apt-get update
apt-get install -y ca-certificates curl gnupg ufw
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

echo "==> Configuring firewall..."
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

echo "==> Creating app directory: ${APP_DIR}"
mkdir -p "${APP_DIR}"

cat <<EOF

Bootstrap complete.

Next steps:
1. Copy these files to ${APP_DIR}:
   - docker-compose.yml
   - Caddyfile
   - .env (from .env.example)

2. Point your DNS A record for DOMAIN to this server's IP.

3. Log in to GHCR (if the image is private):
   echo <GITHUB_PAT> | docker login ghcr.io -u <github-user> --password-stdin

4. Start the stack:
   cd ${APP_DIR}
   docker compose pull
   docker compose up -d

5. Add GitHub secrets for automatic deploy:
   HETZNER_SSH_HOST, HETZNER_SSH_USER, HETZNER_SSH_PRIVATE_KEY, GHCR_PULL_TOKEN

EOF
