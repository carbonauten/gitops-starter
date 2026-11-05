// Self-hosted mail server (Mailcow) on Hetzner Cloud - dedicated VM so
// SMTP/IMAP traffic and mail storage are isolated from the other services in
// this repo, and from the Azure/Alibaba resources in main.tf/content-hub.tf.
//
// Chose Hetzner over Azure here specifically for its simple API-token auth
// (no az-login-style OAuth flow) and because it's commonly used for
// self-hosted Mailcow in practice. EU (German) data centers.
//
// After `terraform apply` succeeds, there are still manual steps - see
// infra/mailcow/README.md: requesting port 25 be unblocked (Hetzner blocks
// it by default for new accounts, like most VPS providers), pointing DNS at
// the output IP, finishing the Mailcow web setup, and creating an API key to
// paste into the platform's Administration -> Mail server page.
// (hcloud is declared in main.tf's single required_providers block - Terraform
// only allows one per module.)

variable "hcloud_token" {
  description = "Hetzner Cloud API token (Console -> your project -> Security -> API Tokens -> generate, Read & Write)."
  type        = string
  sensitive   = true
}

variable "mail_server_fqdn" {
  description = "Public hostname for the mail server, e.g. mail.carbonauten.com. Must resolve to mail_server_public_ip's output once you add the DNS record."
  type        = string
}

variable "mail_server_allowed_ssh_cidr" {
  description = "CIDR allowed to SSH into the mail server (your office/VPN range - never leave this open to the internet). No default on purpose."
  type        = string
}

variable "mail_server_ssh_public_key" {
  description = "Public SSH key (contents of e.g. ~/.ssh/id_ed25519.pub) for the admin login."
  type        = string
}

variable "mail_server_type" {
  description = "Hetzner server type. cx22 (2 vCPU/4GB) is enough for a handful of mailboxes; go larger for more volume/mailboxes."
  type        = string
  default     = "cx22"
}

variable "mail_server_location" {
  description = "Hetzner data center location."
  type        = string
  default     = "fsn1" # Falkenstein, Germany
}

variable "mail_server_enable_backups" {
  description = "Enable Hetzner's automatic daily server backups (rolling 7-day retention, costs +20% of server price). Covers the server's local disk only - NOT the attached mail_data volume, which has its own backup story (see mail_server.tf comments and infra/mailcow/README.md)."
  type        = bool
  default     = true
}

variable "mail_server_volume_size_gb" {
  description = "Size of the separate Hetzner Volume mail data (and Docker's own storage) lives on, in GB. Resizable later via this variable + terraform apply (grow-only)."
  type        = number
  default     = 20
}

provider "hcloud" {
  token = var.hcloud_token
}

resource "hcloud_ssh_key" "mail_server" {
  name       = "mail-server-admin-key"
  public_key = var.mail_server_ssh_public_key
}

resource "hcloud_firewall" "mail_server" {
  name = "mail-server-firewall"

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "22"
    source_ips = [var.mail_server_allowed_ssh_cidr]
  }

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "25"
    source_ips = ["0.0.0.0/0", "::/0"]
  }

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "80"
    source_ips = ["0.0.0.0/0", "::/0"]
  }

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "443"
    source_ips = ["0.0.0.0/0", "::/0"]
  }

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "465"
    source_ips = ["0.0.0.0/0", "::/0"]
  }

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "587"
    source_ips = ["0.0.0.0/0", "::/0"]
  }

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "993"
    source_ips = ["0.0.0.0/0", "::/0"]
  }

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "4190"
    source_ips = ["0.0.0.0/0", "::/0"]
  }
}

// Mail data (and Docker's own storage, so mailcow's named volumes end up
// here too) lives on this separate volume rather than the server's local
// disk - the volume survives a server rebuild, and growing storage is a
// volume resize (mail_server_volume_size_gb + apply) instead of a server
// resize. Trade-off: Hetzner's automatic server backups (below) do NOT cover
// attached volumes - this volume's data protection is the cron-scheduled
// mailcow backup script in the cloud-init template, written to this same
// volume. That protects against application-level mistakes, not against
// losing the volume itself; true disaster recovery needs an off-server copy
// (e.g. a Hetzner Storage Box) - not set up here, see infra/mailcow/README.md.
resource "hcloud_volume" "mail_data" {
  name     = "mail-server-data"
  size     = var.mail_server_volume_size_gb
  location = var.mail_server_location
  format   = "ext4"
}

resource "hcloud_server" "mail_server" {
  name         = "mail-server"
  server_type  = var.mail_server_type
  location     = var.mail_server_location
  image        = "ubuntu-22.04"
  ssh_keys     = [hcloud_ssh_key.mail_server.id]
  firewall_ids = [hcloud_firewall.mail_server.id]
  # Native Hetzner server backups (rolling daily, 7-day retention). Covers the
  # server's local disk only - see hcloud_volume.mail_data's comment above for
  # why mail data itself needs a different backup path.
  backups = var.mail_server_enable_backups

  user_data = templatefile("${path.module}/templates/mailcow_cloud_init.yaml.tpl", {
    mail_server_fqdn = var.mail_server_fqdn
    mail_data_device = hcloud_volume.mail_data.linux_device
  })
}

resource "hcloud_volume_attachment" "mail_data" {
  volume_id = hcloud_volume.mail_data.id
  server_id = hcloud_server.mail_server.id
  # Mounted explicitly by the cloud-init script instead (fixed path, and it
  # needs to happen before Docker installs so Docker's data-root can point at
  # it) rather than Hetzner's own automount, which uses an ID-based path.
  automount = false
}

resource "hcloud_rdns" "mail_server_ipv4" {
  server_id  = hcloud_server.mail_server.id
  ip_address = hcloud_server.mail_server.ipv4_address
  dns_ptr    = var.mail_server_fqdn
}

output "mail_server_public_ip" {
  description = "Point your DNS A record (mail_server_fqdn) at this IP, plus MX/SPF/DKIM/DMARC per infra/mailcow/README.md."
  value       = hcloud_server.mail_server.ipv4_address
}

output "mail_server_volume_id" {
  description = "Hetzner Volume ID holding mail data - survives server rebuilds/deletes independently."
  value       = hcloud_volume.mail_data.id
}

output "mail_server_ssh_command" {
  value = "ssh root@${hcloud_server.mail_server.ipv4_address}"
}
