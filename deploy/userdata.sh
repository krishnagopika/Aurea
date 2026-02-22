#!/bin/bash
set -euo pipefail
exec > /var/log/aurea-init.log 2>&1

echo "=== Aurea EC2 bootstrap $(date) ==="

# Install Docker
dnf update -y
dnf install -y docker git aws-cli
systemctl enable --now docker
usermod -aG docker ec2-user

# Install Docker Compose V2 plugin
mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64" \
     -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

echo "Docker: $(docker --version)"
echo "Compose: $(docker compose version)"

# Pull source code
git clone https://github.com/krishnagopika/Aurea.git /opt/aurea
cd /opt/aurea

# Fetch .env from S3 using EC2 IAM role (no hardcoded keys)
aws s3 cp s3://aurea-config-hacklondon/backend.env /opt/aurea/backend/.env
echo "=== .env fetched from S3 ==="

# Build and start all containers
docker compose up -d --build

PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)
echo "=== Aurea is up at http://${PUBLIC_IP} ==="
