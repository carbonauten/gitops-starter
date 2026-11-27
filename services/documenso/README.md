# documenso

Self-hosted [Documenso](https://documenso.com) (open source, AGPL) - gives
content-hub's file manager ("Dateien" tab) in-app digital signing instead of
a separate external tool. content-hub's backend
(`backend/app/documenso_service.py` + `backend/app/routes/documenso.py`)
talks to this service's REST API and receives a completion webhook back;
see those files for the integration itself.

## ⚠️ Not yet verified against a real instance

This service and the content-hub integration were built without access to a
live, deployed Documenso instance. Two things in particular **must** be
checked once this is actually deployed, before relying on it in production -
see the PR description for the full list:

1. Whether **embedded (iframe) signing** is available on a self-hosted
   instance for free, or gated behind Documenso's paid "Teams" plan (this is
   documented as a plan-gated feature for the hosted product; undocumented
   either way for self-hosting). `DocumentSignPanel.tsx`'s `forceExternal`
   prop is the fallback (`window.open()` in a new tab instead of an iframe)
   if it turns out to be gated.
2. The exact **signed-PDF download endpoint**
   (`documenso_service.download_signed_pdf()`) - best guess based on
   Documenso's "migrate to envelopes" docs, not confirmed against a real
   response.

## One-time Railway setup

This directory is deployed as its own Railway service (same repo, root
directory `services/documenso`):

1. In the Railway project, **New Service → Deploy from GitHub repo**, same
   repo as `content-hub`, root directory `services/documenso`.
2. **Add a PostgreSQL plugin** for this service (Documenso needs its own
   database - do **not** reuse content-hub's Postgres). Link its
   `DATABASE_URL` reference as `NEXT_PRIVATE_DATABASE_URL` below.
3. **Generate a public domain** for this service - unlike
   `services/signal-cli-rest-api`, both content-hub's backend (webhook calls,
   API calls) and the end user's *browser* (embedded/external signing) need
   to reach it.
4. Set the environment variables below.
5. Once deployed, set `DOCUMENSO_BASE_URL` on the **content-hub** service to
   this service's public URL, plus `DOCUMENSO_API_KEY` (create one in
   Documenso's UI under Team Settings → API Tokens, once you've logged in)
   and `DOCUMENSO_WEBHOOK_SECRET` (any random string - configure the same
   value as this service's webhook secret in Documenso's UI, pointed at
   `https://<content-hub-domain>/api/documenso/webhook`).

## Environment variables (this service)

| Variable | Value | Notes |
|----------|-------|-------|
| `NEXTAUTH_SECRET` | `openssl rand -hex 32` | session signing secret |
| `NEXT_PRIVATE_ENCRYPTION_KEY` | `openssl rand -hex 32` | at-rest field encryption |
| `NEXT_PRIVATE_ENCRYPTION_SECONDARY_KEY` | `openssl rand -hex 32` | key rotation slot, required even unused |
| `NEXT_PUBLIC_WEBAPP_URL` | this service's public URL | e.g. `https://documenso-production.up.railway.app` |
| `NEXT_PRIVATE_INTERNAL_WEBAPP_URL` | same as above, or the Railway-internal URL | used for server-to-server calls |
| `NEXT_PRIVATE_DATABASE_URL` | Postgres plugin reference | **this service's own** Postgres, not content-hub's |
| `NEXT_PRIVATE_SIGNING_LOCAL_FILE_PATH` | `/tmp/cert.p12` | see "Signing certificate" below |
| `NEXT_PRIVATE_SIGNING_PASSPHRASE` | the passphrase used when generating the `.p12` | |
| `DOCUMENSO_CERT_P12_BASE64` | base64 of the `.p12` file | decoded to `NEXT_PRIVATE_SIGNING_LOCAL_FILE_PATH` at container start - see `docker-entrypoint.sh` |

**SMTP (Strato, per the user's existing WordPress hosting)** - needed so
Documenso can email signing requests/notifications. Real credentials are
still pending from the user; set placeholders until then:

| Variable | Value |
|----------|-------|
| `NEXT_PRIVATE_SMTP_HOST` | e.g. `smtp.strato.de` |
| `NEXT_PRIVATE_SMTP_PORT` | `587` |
| `NEXT_PRIVATE_SMTP_USERNAME` | e.g. `noreply@elphen.ag` |
| `NEXT_PRIVATE_SMTP_PASSWORD` | mailbox password |
| `NEXT_PRIVATE_SMTP_FROM_ADDRESS` | e.g. `noreply@elphen.ag` |
| `NEXT_PRIVATE_SMTP_FROM_NAME` | e.g. `elphen` |

> Note: content-hub's own `DEPLOY-RAILWAY.md` flags that **Railway
> Hobby/Free plans block outbound SMTP (port 587)** for *that* service's own
> email delivery. Check whether the same restriction applies to this service
> on whatever Railway plan is used - if so, SMTP relay via an HTTPS API
> (e.g. a provider that accepts mail over HTTPS rather than SMTP) would be
> needed instead, same as content-hub's own Resend fallback.

## Signing certificate (self-signed `.p12`)

A self-signed certificate is **not** an eIDAS-qualified signature - Adobe
Reader and similar viewers will show the signature as "not trusted/verified"
(no trusted CA signed it). This is acceptable for internal sign-offs, not
for legally binding external contracts requiring qualified signatures.

Generate it once, locally:

```sh
openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 3650 -nodes \
  -subj "/CN=elphen.ag/O=Elphen AG/C=DE"
openssl pkcs12 -export -out cert.p12 -inkey key.pem -in cert.pem \
  -passout pass:<choose-a-passphrase>
base64 -i cert.p12 | tr -d '\n'
```

Set the base64 output as `DOCUMENSO_CERT_P12_BASE64`, and the passphrase you
chose as `NEXT_PRIVATE_SIGNING_PASSPHRASE`. Keep `key.pem`/`cert.pem`/
`cert.p12` out of version control.
