#!/usr/bin/env bash
# Install the IEC 61499 runtime (Eclipse 4diac FORTE with the module types, in Docker) on a
# Raspberry Pi or another 64-bit ARM Linux.
#
#   curl -fsSL https://raw.githubusercontent.com/AAUSmartProductionLab/iec61499-mgmt-py/main/runtime/install.sh | bash
#
# FORTE then runs as the container "forte" in ~/forte, restarts after a reboot, and loads the
# program in ~/forte/boot/forte.fboot (empty at first: deploy one with modsync push, see
# aas61499-tools/install.sh). Management port 61499 (no authentication: lab network only),
# OPC UA port 4840. Run the script again to update FORTE; the program is kept.
#
# Settings (environment variables):
#   FORTE_FILE  a FORTE binary already on this machine, instead of downloading one
#   FORTE_URL   where to download it (default: asset forte-aarch64 of the latest GitHub release)
#   FORTE_DIR   install folder (default ~/forte)
#   REF         branch or tag the container files are taken from (default main)
set -euo pipefail

REPO="${REPO:-AAUSmartProductionLab/iec61499-mgmt-py}"
REF="${REF:-main}"
FORTE_DIR="${FORTE_DIR:-$HOME/forte}"
FORTE_URL="${FORTE_URL:-https://github.com/$REPO/releases/latest/download/forte-aarch64}"
RAW="https://raw.githubusercontent.com/$REPO/$REF"

say() { printf '\033[1m==> %s\033[0m\n' "$*"; }
fail() { printf 'install: %s\n' "$*" >&2; exit 1; }

# --- what the machine must have -------------------------------------------------------------
arch="$(uname -m)"
if [ "$arch" != aarch64 ] && [ -z "${FORTE_FILE:-}" ]; then
    fail "this machine is $arch; the released FORTE is built for aarch64 (set FORTE_FILE to use your own build)"
fi
command -v curl >/dev/null || fail "curl is missing (sudo apt install curl)"
command -v docker >/dev/null || fail "Docker is missing. Install it and log in again:
    curl -fsSL https://get.docker.com | sudo sh && sudo usermod -aG docker \$USER"
docker compose version >/dev/null 2>&1 || fail "the Docker compose plugin is missing (sudo apt install docker-compose-plugin)"
docker info >/dev/null 2>&1 || fail "cannot reach Docker as $(id -un). Add yourself to the docker group and log in again:
    sudo usermod -aG docker \$USER"
# A clock that is far off breaks the download of the base image (certificate dates).
if [ "$(date +%Y)" -lt 2026 ]; then
    fail "the system clock is wrong ($(date)); set it first (sudo timedatectl set-ntp true)"
fi

# --- files -----------------------------------------------------------------------------------
say "Installing FORTE in $FORTE_DIR"
mkdir -p "$FORTE_DIR/boot"
[ -e "$FORTE_DIR/boot/forte.fboot" ] || : > "$FORTE_DIR/boot/forte.fboot"

# Next to this script in a checkout, the container files are taken from it; piped from curl, downloaded.
here="$(cd "$(dirname "${BASH_SOURCE[0]:-/nonexistent/x}")" 2>/dev/null && pwd || true)"
for file in Dockerfile compose.yaml .dockerignore; do
    if [ -n "$here" ] && [ -f "$here/../deploy/pi/$file" ]; then
        cp "$here/../deploy/pi/$file" "$FORTE_DIR/$file"
    else
        curl -fsSL "$RAW/deploy/pi/$file" -o "$FORTE_DIR/$file" || fail "cannot download deploy/pi/$file from $RAW"
    fi
done

if [ -n "${FORTE_FILE:-}" ]; then
    say "Using $FORTE_FILE"
    cp "$FORTE_FILE" "$FORTE_DIR/forte.new"
else
    say "Downloading FORTE from $FORTE_URL"
    curl -fL --progress-bar "$FORTE_URL" -o "$FORTE_DIR/forte.new" || fail "cannot download FORTE.
    Publish the binary as the asset forte-aarch64 of a GitHub release (runtime/package-release.ps1),
    or copy it here and set FORTE_FILE."
    if curl -fsSL "$FORTE_URL.sha256" -o "$FORTE_DIR/forte.sha256" 2>/dev/null; then
        expected="$(cut -d' ' -f1 "$FORTE_DIR/forte.sha256")"
        actual="$(sha256sum "$FORTE_DIR/forte.new" | cut -d' ' -f1)"
        [ "$expected" = "$actual" ] || fail "the downloaded FORTE does not match its checksum"
        say "Checksum verified"
    fi
fi
chmod +x "$FORTE_DIR/forte.new"
mv "$FORTE_DIR/forte.new" "$FORTE_DIR/forte"

# --- container -------------------------------------------------------------------------------
say "Building and starting the container"
(cd "$FORTE_DIR" && docker compose up -d --build --force-recreate)

for _ in $(seq 1 40); do
    if (exec 3<>/dev/tcp/127.0.0.1/61499) 2>/dev/null; then up=1; break; fi
    sleep 0.5
done
[ -n "${up:-}" ] || fail "FORTE does not answer on port 61499; see: cd $FORTE_DIR && docker compose logs"

say "FORTE is running"
echo "  management  $(hostname -I 2>/dev/null | cut -d' ' -f1):61499"
echo "  OPC UA      opc.tcp://$(hostname -I 2>/dev/null | cut -d' ' -f1):4840"
echo "  container   cd $FORTE_DIR && docker compose ps | logs -f | restart | stop"
[ -d /sys/class/pwm/pwmchip0 ] || echo "  note        no PWM channels: add 'dtoverlay=pwm-2chan' to /boot/firmware/config.txt and reboot (servo, motor speed)"
[ -s "$FORTE_DIR/boot/forte.fboot" ] || echo "  next        no program yet: install the tools and run 'modsync push <module> --target pi --host localhost'"
