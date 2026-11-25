# Thin wrapper around the community signal-cli-rest-api image so this
# service can live in this repo and deploy like the others. See README.md
# in this directory for the one-time Railway setup (volume + env var).
FROM bbernhard/signal-cli-rest-api:0.95

# "normal" mode: no json-rpc daemon, simplest send/receive over plain HTTP.
ENV MODE=normal

EXPOSE 8080
