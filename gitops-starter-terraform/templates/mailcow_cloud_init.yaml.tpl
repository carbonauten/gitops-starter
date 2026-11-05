#cloud-config
# Bootstraps Docker + mailcow-dockerized on first boot, with mail data (and
# Docker's own storage) living on the attached Hetzner Volume rather than the
# server's local disk - so mail survives a server rebuild and growing storage
# is a volume resize, not a server resize. Mailcow itself still needs a few
# manual steps after this runs - see infra/mailcow/README.md:
#   1. Open https://${mail_server_fqdn} and finish setup there
#   2. Add the DNS records printed by generate_config.sh / listed in the README
#   3. Log in to Mailcow's admin UI, create an API key, paste it into
#      app.carbonauten.com -> Administration -> Mail server
package_update: true
package_upgrade: true

packages:
  - ca-certificates
  - curl
  - gnupg
  - ufw
  - e2fsprogs

write_files:
  - path: /opt/mount-mail-volume.sh
    permissions: "0755"
    content: |
      #!/usr/bin/env bash
      set -euo pipefail

      DEVICE="${mail_data_device}"
      MOUNT_POINT="/mnt/mail-data"

      # The volume attaches via a separate Hetzner API call than the one that
      # creates the server, so it may not be visible yet when cloud-init first
      # runs this - wait rather than fail.
      for i in $(seq 1 60); do
        [ -b "$DEVICE" ] && break
        sleep 2
      done
      [ -b "$DEVICE" ] || { echo "mail data device $DEVICE never appeared" >&2; exit 1; }

      mkdir -p "$MOUNT_POINT"

      # Only format on first-ever use - this volume outlives server rebuilds,
      # so re-formatting an already-initialized volume would destroy mail data.
      if ! blkid "$DEVICE" > /dev/null 2>&1; then
        mkfs.ext4 -F "$DEVICE"
      fi

      grep -q "$DEVICE" /etc/fstab || echo "$DEVICE $MOUNT_POINT ext4 discard,nofail,defaults 0 0" >> /etc/fstab
      mountpoint -q "$MOUNT_POINT" || mount "$MOUNT_POINT"

  - path: /opt/mailcow-setup.sh
    permissions: "0755"
    content: |
      #!/usr/bin/env bash
      set -euo pipefail

      bash /opt/mount-mail-volume.sh

      # Point Docker's own storage at the volume too, so mailcow's named
      # volumes (where the actual mail/DB data lives) end up there - must be
      # set before Docker is installed/started for the first time.
      mkdir -p /mnt/mail-data/docker
      mkdir -p /etc/docker
      if [ ! -f /etc/docker/daemon.json ]; then
        printf '{\n  "data-root": "/mnt/mail-data/docker"\n}\n' > /etc/docker/daemon.json
      fi

      # Docker Engine + Compose plugin (official repo, not distro package)
      install -m 0755 -d /etc/apt/keyrings
      curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
      chmod a+r /etc/apt/keyrings/docker.asc
      echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
        > /etc/apt/sources.list.d/docker.list
      apt-get update
      apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

      mkdir -p /mnt/mail-data/mailcow
      ln -sfn /mnt/mail-data/mailcow /opt/mailcow
      cd /opt/mailcow
      if [ ! -d mailcow-dockerized ]; then
        git clone https://github.com/mailcow/mailcow-dockerized
      fi
      cd mailcow-dockerized

      if [ ! -f mailcow.conf ]; then
        # generate_config.sh's only required interactive input is the FQDN;
        # feeding it as an env var skips that one prompt.
        MAILCOW_HOSTNAME="${mail_server_fqdn}" ./generate_config.sh
      fi

      docker compose pull
      docker compose up -d

      echo "mailcow bootstrap done - open https://${mail_server_fqdn} to finish setup" \
        > /mnt/mail-data/BOOTSTRAP_DONE

  - path: /opt/mailcow-backup.sh
    permissions: "0755"
    content: |
      #!/usr/bin/env bash
      # Daily application-level backup via mailcow's own script, kept on the
      # same volume. This protects against mailcow-level mistakes (bad config
      # change, accidental deletion) but NOT against losing the volume itself -
      # for real disaster recovery, also copy /mnt/mail-data/backups
      # off this server periodically (e.g. to a Hetzner Storage Box or S3-
      # compatible target). Not set up here - see infra/mailcow/README.md.
      set -euo pipefail
      cd /opt/mailcow/mailcow-dockerized
      export MAILCOW_BACKUP_LOCATION=/mnt/mail-data/backups
      ./helper-scripts/backup_and_restore.sh backup all --delete-days 14

  - path: /etc/cron.d/mailcow-backup
    permissions: "0644"
    content: |
      15 3 * * * root /opt/mailcow-backup.sh >> /var/log/mailcow-backup.log 2>&1

  - path: /etc/ufw/applications.d/mailcow
    permissions: "0644"
    content: |
      [mailcow]
      title=Mailcow mail server
      description=SMTP/IMAP/Submission/HTTPS for mailcow-dockerized
      ports=25,80,110,143,443,465,587,993,995,4190/tcp

runcmd:
  - [ ufw, allow, OpenSSH ]
  - [ ufw, allow, mailcow ]
  - [ ufw, --force, enable ]
  - [ bash, /opt/mailcow-setup.sh ]
