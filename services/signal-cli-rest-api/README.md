# signal-cli-rest-api

Self-hosted wrapper around [bbernhard/signal-cli-rest-api](https://github.com/bbernhard/signal-cli-rest-api),
an unofficial, community-maintained HTTP wrapper around `signal-cli`. Signal
has no public OAuth/API of its own, so the content-hub's Signal integration
(`backend/app/signal_service.py`) talks to this sidecar instead: a user's
personal Signal account is linked as a secondary device (QR code, scanned
from the Signal app), and messages are then sent/received via this
container's REST API.

## One-time Railway setup

This directory is deployed as its own Railway service (same repo, root
directory `services/signal-cli-rest-api`):

1. In the Railway project, **New Service → Deploy from GitHub repo**, same
   repo as `content-hub`, root directory `services/signal-cli-rest-api`.
2. **Add a volume** mounted at `/home/.local/share/signal-cli` — this is
   where signal-cli persists linked-device state. Without a volume, every
   redeploy forces re-linking (re-scanning the QR code).
3. Once deployed, copy this service's **internal** Railway URL (e.g.
   `http://signal-cli.railway.internal:8080`) and set it as the
   `SIGNAL_CLI_REST_API_URL` environment variable on the **content-hub**
   service (not on this one).
4. No inbound public traffic is needed — content-hub talks to this service
   over Railway's private network, so this service does not need a public
   domain.

## Notes

- "Normal" mode (`MODE=normal` in the Dockerfile) keeps things simple: no
  background json-rpc daemon, just synchronous HTTP calls for linking,
  sending and receiving.
- Multiple users can each link their own phone number against the same
  container — signal-cli-rest-api addresses accounts by phone number in the
  URL path, so one instance serves everyone.
- This is an unofficial integration, not sanctioned by Signal. Treat it as
  best-effort; Signal could change something that breaks `signal-cli` at
  any time.
