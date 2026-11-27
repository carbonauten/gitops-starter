# Self-hosted Documenso (https://documenso.com, AGPL) - gives content-hub's
# file manager in-app digital signing (backend/app/documenso_service.py +
# backend/app/routes/documenso.py). See README.md in this directory for the
# one-time Railway setup (Postgres plugin, env vars, self-signed cert).
#
# Pinned to the "latest" tag available at the time this was written
# (2026-11-27) - bump deliberately, Documenso ships frequently.
FROM documenso/documenso:v2.22.0

# The upstream image's CMD is `sh start.sh`, run as the unprivileged
# `nodejs` user (uid 1001) from /app/apps/remix - see
# https://github.com/documenso/documenso/blob/main/docker/Dockerfile.
# Railway has no volume mounts for build-time secrets, so the self-signed
# signing certificate (see README.md for how to generate it) is passed in
# base64-encoded as the DOCUMENSO_CERT_P12_BASE64 env var and decoded to
# /tmp/cert.p12 (world-writable, unlike most of this image's filesystem) at
# container start - the standard "secret via env var" workaround for PaaS
# platforms without custom secret-file mounts. Set
# NEXT_PRIVATE_SIGNING_LOCAL_FILE_PATH=/tmp/cert.p12 to match.
WORKDIR /app/apps/remix

COPY docker-entrypoint.sh ./docker-entrypoint.sh
USER root
RUN chmod +x ./docker-entrypoint.sh && chown nodejs:nodejs ./docker-entrypoint.sh
USER nodejs

CMD ["sh", "docker-entrypoint.sh"]
