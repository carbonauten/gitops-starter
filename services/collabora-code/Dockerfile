# Collabora Online (CODE) - the LibreOffice-based editor that content-hub's
# WOPI host (backend/app/wopi_service.py, backend/app/routes/wopi.py) talks
# to. See README.md in this directory for the Railway setup this needs.
FROM collabora/code:24.04.12.4.1

# Collabora's document-isolation sandbox (per-file chroot jails) needs the
# MKNOD capability, which Railway's build/runtime doesn't let a service
# request. --o:mount_jail_tree=false disables that sandboxing instead -
# the standard workaround for PaaS platforms without custom cap-add.
# ssl.enable=false + ssl.termination=true: Railway's edge already
# terminates TLS, so Collabora itself should speak plain HTTP.
ENV extra_params="--o:mount_jail_tree=false --o:ssl.enable=false --o:ssl.termination=true"

# REQUIRED: set this in Railway's service variables to a regex matching
# content-hub's public domain, dots escaped, e.g. content-hub-production\.up\.railway\.app
# Collabora refuses WOPI hosts that don't match this. See README.md.
ENV domain=""

EXPOSE 9980
