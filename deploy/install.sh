#!/usr/bin/env bash
# Run on a dedicated Ubuntu 24.04 EC2 instance: sudo bash deploy/install.sh
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo 'Run with sudo: sudo bash deploy/install.sh' >&2
    exit 1
fi

source_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
app_dir=/var/www/aws-authenticator
data_dir=/var/lib/aws-authenticator

# This configuration uses Ubuntu's system Python, matching apt's mod_wsgi.
source /etc/os-release
if [[ "$ID" != ubuntu || "$VERSION_ID" != 24.04 ]]; then
    echo 'This installer is intended for Ubuntu Server 24.04 LTS.' >&2
    exit 1
fi
if [[ ! -f "$source_dir/frontend/dist/index.html" ]]; then
    echo 'React build is missing. Run npm run build locally and upload the deployment ZIP.' >&2
    exit 1
fi
if [[ "$source_dir" == "$app_dir" ]]; then
    echo 'Extract the package under /home/ubuntu/aws-authenticator before running this installer.' >&2
    exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y apache2 libapache2-mod-wsgi-py3 python3 python3-pip python3-venv sqlite3

install -d -m 755 "$app_dir" "$app_dir/backend" "$app_dir/frontend"
install -m 644 "$source_dir/backend/"*.py "$source_dir/backend/schema.sql" "$app_dir/backend/"
install -m 644 "$source_dir/requirements.txt" "$source_dir/wsgi.py" "$app_dir/"
# Clear only the old compiled UI at this fixed, verified installation path.
if [[ -d "$app_dir/frontend/dist" ]]; then
    rm -rf -- /var/www/aws-authenticator/frontend/dist
fi
cp -r "$source_dir/frontend/dist" "$app_dir/frontend/dist"
chmod -R a+rX "$app_dir/frontend/dist"

/usr/bin/python3 -m venv "$app_dir/.venv"
"$app_dir/.venv/bin/python" -m pip install --disable-pip-version-check -r "$app_dir/requirements.txt"
install -d -o www-data -g www-data -m 750 "$data_dir"

# A persistent secret outside the code directory; preserve it during updates.
if [[ ! -f /etc/aws-authenticator.env ]]; then
    /usr/bin/python3 - <<'PY'
import os
import secrets
from pathlib import Path

os.umask(0o077)
Path('/etc/aws-authenticator.env').write_text(
    'APP_ENV=production\n'
    f'SECRET_KEY={secrets.token_hex(32)}\n'
    'DATABASE_PATH=/var/lib/aws-authenticator/users.db\n'
    'COOKIE_SECURE=false\n',
    encoding='utf-8',
)
PY
fi
chown root:www-data /etc/aws-authenticator.env
chmod 640 /etc/aws-authenticator.env

cd "$app_dir"
sudo -u www-data "$app_dir/.venv/bin/python" -c 'from wsgi import application; print("Flask loaded; SQLite tables ready.")'

install -m 644 "$source_dir/deploy/apache.conf" /etc/apache2/sites-available/aws-authenticator.conf
a2enmod wsgi
a2dissite 000-default
a2ensite aws-authenticator
apache2ctl configtest
systemctl enable apache2
systemctl restart apache2

echo 'Deployment complete. Open http://YOUR_EC2_PUBLIC_DNS or http://YOUR_EC2_PUBLIC_IP.'
echo 'Verify: curl http://127.0.0.1/api/health'
