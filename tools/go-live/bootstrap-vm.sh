#!/usr/bin/env bash
# One-time setup of a fresh Ubuntu 22.04/24.04 server for Borewell.
# Run it ON THE SERVER, from inside the cloned repo:
#     git clone https://github.com/AegixHQ/borewell-platform && cd borewell-platform
#     bash tools/go-live/bootstrap-vm.sh
# Safe to run again. It installs Docker + the few tools the Makefile needs,
# adds a small swap file (image builds on a 4 GB machine are happier with it)
# and then tells you the next command. It does not touch your .env.prod.
set -euo pipefail

if [ "$(id -u)" -eq 0 ]; then SUDO=""; else SUDO="sudo"; fi

if ! grep -qiE 'ubuntu|debian' /etc/os-release; then
  echo "This script is for Ubuntu/Debian servers." >&2; exit 1
fi

echo "== 1/4 System packages =="
$SUDO apt-get update -y
$SUDO DEBIAN_FRONTEND=noninteractive apt-get upgrade -y
$SUDO DEBIAN_FRONTEND=noninteractive apt-get install -y git make python3 curl ca-certificates

echo "== 2/4 Docker =="
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | $SUDO sh
fi
$SUDO systemctl enable --now docker
if [ "$(id -u)" -ne 0 ]; then $SUDO usermod -aG docker "$USER"; fi

echo "== 3/4 Swap (2 GB, only if the server has none) =="
if [ "$(swapon --show --noheadings | wc -l)" -eq 0 ]; then
  $SUDO fallocate -l 2G /swapfile
  $SUDO chmod 600 /swapfile
  $SUDO mkswap /swapfile >/dev/null
  $SUDO swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' | $SUDO tee -a /etc/fstab >/dev/null
else
  echo "swap already present"
fi

echo "== 4/4 Checks =="
$SUDO docker --version
$SUDO docker compose version
free -h | sed -n 1,2p
PUBIP="$(curl -fsS -m 5 https://api.ipify.org || echo '<unknown>')"
echo
echo "Done. This server's public IP: $PUBIP"
echo
echo "NEXT:"
echo "  1. Point your DuckDNS name at $PUBIP and make sure ports 80 and 443 are open"
echo "     in the cloud provider's firewall."
if [ "$(id -u)" -ne 0 ]; then
  echo "  2. Log out and back in once (so 'docker' works without sudo)."
  echo "  3. cd ~/borewell-platform   (or wherever you cloned it)"
else
  echo "  2. cd into the cloned borewell-platform folder"
fi
echo "  4. make prod-init DOMAIN=<your-name>.duckdns.org EMAIL=<you@example.com>"
echo "  5. nano .env.prod     (fill the Razorpay + admin lines)"
echo "  6. make prod-check && make prod-deploy"
