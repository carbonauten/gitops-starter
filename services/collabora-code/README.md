# collabora-code

Self-hosted [Collabora Online (CODE)](https://www.collaboraoffice.com/code/) -
the actual LibreOffice rendering/editing engine, exposed over HTTP and the
WOPI protocol. This is what gives content-hub's "Files" page *real* live
editing of Office documents (Word/Excel/PowerPoint/ODF), instead of
Microsoft's read-only online viewer.

content-hub's own backend (`backend/app/wopi_service.py` +
`backend/app/routes/wopi.py`) acts as the **WOPI host**: Collabora calls it
to fetch/save file bytes, content-hub never talks to Collabora's internals
directly beyond building the editor URL the frontend loads in an iframe.

## One-time Railway setup

Unlike `services/signal-cli-rest-api` (internal-only), this service needs a
**public** domain, because the user's *browser* loads the editor UI and
opens a WebSocket directly against Collabora - not just content-hub's
backend.

1. **New Service → Deploy from GitHub repo**, same repo, root directory
   `services/collabora-code`.
2. **Generate a public domain** for this service in Railway's networking
   settings (e.g. `collabora-production.up.railway.app`).
3. Set the **`domain`** environment variable on *this* service to a regex
   matching content-hub's public domain, with literal dots escaped, e.g.:
   ```
   domain=content-hub-production\.up\.railway\.app
   ```
   Collabora only accepts WOPI hosts matching this - get it wrong and every
   document load fails with a generic error from the Collabora side.
4. On the **content-hub** service, set `COLLABORA_URL` to this service's
   public URL, e.g. `https://collabora-production.up.railway.app`.
5. Open a platform-stored Office document from Files - it should now open
   as a live, editable LibreOffice session instead of the read-only viewer.

## Known limitations (first version)

- **No cross-process lock persistence**: `wopi_service.py` keeps WOPI edit
  locks in an in-memory dict, not the database. Fine with `numReplicas = 1`
  (single instance), but a content-hub redeploy mid-edit silently drops any
  outstanding lock - a second editor opening the file right after a deploy
  could in theory race the first. Low risk for how this is used today;
  worth revisiting (e.g. a `wopi_locks` table) if concurrent editing of the
  same file becomes common.
- **No discovery-XML parsing**: the edit URL is built from Collabora's
  documented stable convenience path (`/browser/dist/cool.html`) rather
  than resolving the exact per-filetype action URL from
  `/hosting/discovery`. This matches current Collabora CODE releases; if a
  future Collabora version removes that alias, the edit URL would need to
  switch to proper discovery-based resolution instead.
- **No proof-key (WOPI signature) verification**: requests to the WOPI host
  are authenticated only by the short-lived, file+user-scoped
  `access_token` - not by validating Collabora's cryptographic proof-key
  headers. Standard, simpler tradeoff for a self-hosted single-tenant setup
  like this one; revisit if the WOPI host is ever exposed beyond this one
  trusted Collabora instance.
- **`--o:mount_jail_tree=false`**: disables Collabora's per-document chroot
  sandbox (needs a Docker capability Railway doesn't expose). Collabora
  still works correctly without it; it's a defense-in-depth layer being
  traded away for deployability, not a feature being lost.
