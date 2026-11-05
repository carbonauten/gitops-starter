# Self-hosted mail server (Mailcow)

This sets up a real mail server with Postfix (SMTP), Dovecot (IMAP), Rspamd
(spam filtering), ClamAV (antivirus), and a web admin UI — running on its own
Hetzner Cloud VM, separate from the Railway-hosted content-hub app. The
content-hub app talks to it over Mailcow's REST API (Administration → Mail
server) to create/delete mailboxes; it does not handle mail delivery itself.

Hetzner was chosen over Azure specifically for its simple API-token
authentication (no `az login`-style OAuth flow needed) and because it's
commonly used for self-hosted Mailcow deployments in practice.

**Nothing here has been run against a live instance.** The Terraform and the
app-side API client (`backend/app/mailcow_service.py`) are written against
Mailcow's documented conventions, but verify each step against your actual
deployment — Mailcow doesn't publish a versioned API contract, and cloud
provider resource schemas change over time.

**Note on this repo's Terraform layout:** there are two separate Terraform
trees in this repo - this one (`infra/terraform/`) and a second,
unrelated one at the repo root (`gitops-starter-terraform/`), which is what
the "Terraform CI" GitHub Actions workflow actually validates. The mail
server resources below live only in `infra/terraform/` and are not covered
by that CI check; validate changes here manually (`terraform validate` from
`infra/terraform/`) before applying.

## Prerequisites

- A Hetzner Cloud account and project, plus an API token: Hetzner Cloud Console → your project → **Security → API Tokens → Generate API Token** (Read & Write). This is a single token, not an OAuth login — copy it somewhere safe, it's only shown once.
- A domain you control the DNS for (e.g. `carbonauten.com`)
- An SSH key pair

## 0. Request port 25 be unblocked

Like virtually all VPS providers, Hetzner blocks outbound port 25 (SMTP) by
default on new accounts/projects to curb spam abuse. Before provisioning,
open a support ticket (Hetzner Cloud Console → Support) asking for SMTP/port
25 to be unblocked for your project, explaining you're running a mail server.
This can take from minutes to a day or two — do it first so it's not blocking
you later.

## 1. Provision the VM

```bash
cd infra/terraform
terraform init
terraform apply \
  -target=hcloud_ssh_key.mail_server \
  -target=hcloud_firewall.mail_server \
  -target=hcloud_server.mail_server \
  -target=hcloud_rdns.mail_server_ipv4 \
  -var="hcloud_token=<your Hetzner API token>" \
  -var="mail_server_fqdn=mail.carbonauten.com" \
  -var="mail_server_allowed_ssh_cidr=<your office/VPN CIDR, e.g. 203.0.113.0/24>" \
  -var="mail_server_ssh_public_key=$(cat ~/.ssh/id_ed25519.pub)"
```

(The `-target` flags scope this apply to just the mail-server resources —
the rest of `main.tf`/`content-hub.tf` targets Azure/Alibaba for other,
unrelated parts of this repo; don't let a plain `terraform apply` with no
`-target` try to also touch those.)

Note the `mail_server_public_ip` output — you need it for the DNS records
below. VM boot takes a few minutes; cloud-init then installs Docker and
mailcow-dockerized automatically (see
`infra/terraform/templates/mailcow_cloud_init.yaml.tpl`). SSH in (`ssh
root@<ip>`, using the private key matching `mail_server_ssh_public_key`) and
check `/opt/mailcow/BOOTSTRAP_DONE` exists before continuing.

## 2. DNS records

Create these at your domain's DNS provider (not something Terraform can do
for you unless your DNS is also hosted in a Terraform-managed provider).
Replace `203.0.113.10` with the real `mail_server_public_ip` output and
`carbonauten.com` with your actual domain.

| Type | Host | Value | Why |
|---|---|---|---|
| A | `mail.carbonauten.com` | `203.0.113.10` | Points the mail server's hostname at the VM |
| MX | `carbonauten.com` | `10 mail.carbonauten.com` | Tells other mail servers where to deliver mail for `@carbonauten.com` |
| TXT (SPF) | `carbonauten.com` | `v=spf1 mx ~all` | Authorizes this server to send mail for the domain |
| TXT (DKIM) | `dkim._domainkey.carbonauten.com` | *(from Mailcow admin UI, see step 3)* | Signs outgoing mail so receivers can verify it wasn't tampered with |
| TXT (DMARC) | `_dmarc.carbonauten.com` | `v=DMARC1; p=quarantine; rua=mailto:postmaster@carbonauten.com` | Tells receivers what to do with mail that fails SPF/DKIM |
| PTR (reverse DNS) | *(set on the IP, not the domain)* | `mail.carbonauten.com` | Terraform sets this via the `hcloud_rdns` resource; some providers need the forward A record to resolve first — re-check after step 1 |

Repeat the MX/SPF/DKIM/DMARC rows per additional domain you want mailboxes on
(e.g. `fuckco2.shop`), once you've added that domain in Mailcow (step 3).

**Expect a reputation ramp-up period.** A brand-new mail server with no
sending history commonly lands in recipients' spam folders for the first
days/weeks, regardless of correct SPF/DKIM/DMARC. Start with low volume.

## 3. Finish setup in the Mailcow web UI

1. Open `https://mail.carbonauten.com` (self-signed cert warning is normal
   until Mailcow's built-in Let's Encrypt step runs — it does this
   automatically once DNS resolves).
2. Log in with the default admin credentials shown during `generate_config.sh`
   (check `/opt/mailcow/mailcow-dockerized/mailcow.conf`), then change the
   password immediately.
3. Add your domain(s) (Configuration → Mail Setup → Domains).
4. Copy the DKIM key Mailcow generates per domain into the DNS TXT record
   from step 2.
5. Create an API key: Configuration → Access → API, enable read/write, and
   restrict the allowed IP to the content-hub backend's outbound IP if you
   know it (Railway's egress IPs aren't static by default — leaving it open
   is a real trade-off worth revisiting once you know your actual egress
   range).

## 4. Connect the platform

In app.carbonauten.com → Administration → Mail server, paste:
- **API URL**: `https://mail.carbonauten.com`
- **API key**: from step 3.5
- **Default domain**: `carbonauten.com`

Until this is filled in, that page shows sample/demo mailboxes so the UI is
still usable to preview during development.

## Ongoing operational responsibility

This is the part a managed provider (M365, Migadu, etc.) would otherwise
carry for you:

- **Security updates**: `apt-get upgrade` + `docker compose pull && docker compose up -d` regularly on the VM.
- **Backups**: Mailcow ships `helper-scripts/backup_and_restore.sh` — schedule it, and store backups off the VM.
- **Blacklist monitoring**: check `mail.carbonauten.com`'s IP against RBLs (e.g. mxtoolbox.com) periodically, especially after any spike in outbound volume.
- **Disk space**: mail accumulates; monitor `/opt/mailcow` usage - the disk size comes bundled with `mail_server_type` (e.g. cx22 includes 40GB). Resize via `mail_server_type` + `terraform apply`, or attach an `hcloud_volume` for more headroom, once you're closer to the limit.
- **Uptime**: nothing in this repo monitors the VM itself; consider adding it to whatever uptime checks you already use for app.carbonauten.com.
