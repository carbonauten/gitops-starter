#cloud-config
# Bootstraps Docker + mailcow-dockerized on first boot. Mailcow itself still
# needs a few manual steps after this runs - see infra/mailcow/README.md:
#   1. SSH in and set the admin password: `docker exec -it mailcowdockerized-dovecot-mailcow-1 ...`
#      (actually: open https://${mail_server_fqdn} and finish setup there)
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

write_files:
  - path: /opt/mailcow-setup.sh
    permissions: "0755"
    content: |
      #!/usr/bin/env bash
      set -euo pipefail

      # Docker Engine + Compose plugin (official repo, not distro package)
      install -m 0755 -d /etc/apt/keyrings
      curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
      chmod a+r /etc/apt/keyrings/docker.asc
      echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
        > /etc/apt/sources.list.d/docker.list
      apt-get update
      apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

      mkdir -p /opt/mailcow
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
        > /opt/mailcow/BOOTSTRAP_DONE

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
