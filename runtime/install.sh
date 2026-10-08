#!/usr/bin/env bash
# Make a Raspberry Pi an IEC 61499 PLC, in one run: Docker if it is missing, the runtime (Eclipse
# 4diac FORTE with the module types) in a container that starts with the machine, and the header's
# GPIO lines and PWM channels for it. For a Raspberry Pi 4 or 5 with a 64-bit Linux (Raspberry Pi
# OS, Ubuntu); the user who runs it needs sudo.
#
#   curl -fsSL https://raw.githubusercontent.com/AAUSmartProductionLab/iec61499-mgmt-py/main/runtime/install.sh | bash
#
# FORTE then runs as the container "forte" in ~/forte, restarts after a reboot, and loads the
# program in ~/forte/boot/forte.fboot (empty at first: deploy one with modsync push, see
# aas61499-tools/install.sh). Management port 61499 (no authentication: lab network only),
# OPC UA port 4840. Run the script again to update FORTE; the program is kept.
#
# Settings (environment variables):
#   FORTE_FILE  a FORTE binary already on this machine, instead of the repository's
#   FORTE_URL   where to download it (default: runtime/bin/forte-aarch64 of the repository)
#   FORTE_DIR   install folder (default ~/forte)
#   REF         branch or tag the files are taken from (default main)
#   PWM         0: leave the boot configuration alone (default 1: enable the two PWM channels)
set -euo pipefail

REPO="${REPO:-AAUSmartProductionLab/iec61499-mgmt-py}"
REF="${REF:-main}"
FORTE_DIR="${FORTE_DIR:-$HOME/forte}"
RAW="https://raw.githubusercontent.com/$REPO/$REF"
FORTE_URL="${FORTE_URL:-$RAW/runtime/bin/forte-aarch64}"
PWM="${PWM:-1}"

say() { printf '\033[1m==> %s\033[0m\n' "$*"; }
fail() { printf 'install: %s\n' "$*" >&2; exit 1; }

SUDO=""
if [ "$(id -u)" != 0 ]; then
    command -v sudo >/dev/null || fail "run this as root, or install sudo"
    SUDO="sudo"
fi
# Packages are installed without questions (a kernel or service restart prompt would hang a piped run).
apt_install() { $SUDO env DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=a apt-get install -y -q "$@"; }

# --- what the machine must have -------------------------------------------------------------
arch="$(uname -m)"
if [ "$arch" != aarch64 ] && [ -z "${FORTE_FILE:-}" ]; then
    fail "this machine is $arch; the FORTE in the repository is built for aarch64 (set FORTE_FILE to use your own build)"
fi
# A clock that is far off breaks every download (certificate dates).
if [ "$(date +%Y)" -lt 2026 ]; then
    fail "the system clock is wrong ($(date)); set it first (sudo timedatectl set-ntp true)"
fi
if ! command -v curl >/dev/null; then
    say "Installing curl"
    $SUDO apt-get update -q && apt_install curl ca-certificates
fi

# --- Docker ----------------------------------------------------------------------------------
have_docker() {
    command -v docker >/dev/null || return 1
    docker compose version >/dev/null 2>&1 || $SUDO docker compose version >/dev/null 2>&1
}
if ! have_docker; then
    say "Installing Docker"
    . /etc/os-release
    if [ "${ID:-}" = ubuntu ]; then
        # Ubuntu carries Docker and the compose plugin itself.
        $SUDO apt-get update -q
        apt_install docker.io docker-compose-v2
    else
        # Raspberry Pi OS, Debian: Docker's own installer (adds Docker's package source).
        curl -fsSL https://get.docker.com | $SUDO sh
    fi
fi
systemctl is-active --quiet docker 2>/dev/null || $SUDO systemctl enable --now docker >/dev/null 2>&1 || true
user="$(id -un)"
if [ "$(id -u)" != 0 ] && ! id -nG "$user" | tr ' ' '\n' | grep -qx docker; then
    say "Adding $user to the group docker (in effect at the next login)"
    $SUDO usermod -aG docker "$user"
fi
# Until that login, Docker is reached through sudo.
if docker info >/dev/null 2>&1; then DOCKER="docker"; else DOCKER="$SUDO docker"; fi
$DOCKER info >/dev/null 2>&1 || fail "Docker does not answer; see: sudo systemctl status docker"
$DOCKER compose version >/dev/null 2>&1 || fail "the Docker compose plugin is missing (sudo apt install docker-compose-v2 or docker-compose-plugin)"

# --- the header's IO -------------------------------------------------------------------------
# The 40-pin header is the GPIO chip of the SoC on a Pi 4 and of the RP1 on a Pi 5, which older
# kernels number 4 there. FORTE's programs use chip 0, so that chip is given to the container as 0.
gpiochip=/dev/gpiochip0
for chip in /sys/bus/gpio/devices/gpiochip*; do
    case "$(readlink -f "$chip" 2>/dev/null)" in
        *1f000d0000.gpio*|*fe200000.gpio*|*7e200000.gpio*) gpiochip="/dev/$(basename "$chip")"; break ;;
    esac
done
[ -e "$gpiochip" ] || fail "no GPIO chip at $gpiochip: is this a Raspberry Pi?"

# Two hardware PWM channels on GPIO18 and GPIO19 (step pulses, motor speed): a device tree overlay,
# in effect after a reboot.
reboot_needed=""
if [ "$PWM" = 1 ] && ! ls /sys/class/pwm/pwmchip* >/dev/null 2>&1; then
    config=/boot/firmware/config.txt
    [ -f "$config" ] || config=/boot/config.txt
    if [ ! -f "$config" ]; then
        echo "  note        no boot configuration found: PWM channels are not set up"
    elif grep -Eq '^dtoverlay=pwm(-2chan)?([,[:space:]]|$)' "$config"; then
        reboot_needed=1                       # enabled before, not booted with yet
    else
        say "Enabling the PWM channels in $config"
        printf '\n# IEC 61499 runtime (runtime/install.sh): PWM on GPIO18 and GPIO19\n[all]\ndtoverlay=pwm-2chan\n' \
            | $SUDO tee -a "$config" >/dev/null
        reboot_needed=1
    fi
fi

# --- files -----------------------------------------------------------------------------------
say "Installing FORTE in $FORTE_DIR"
mkdir -p "$FORTE_DIR/boot"
[ -e "$FORTE_DIR/boot/forte.fboot" ] || : > "$FORTE_DIR/boot/forte.fboot"
printf 'GPIOCHIP=%s\n' "$gpiochip" > "$FORTE_DIR/.env"

# Next to this script in a checkout, the files are taken from it; piped from curl, downloaded.
here="$(cd "$(dirname "${BASH_SOURCE[0]:-/nonexistent/x}")" 2>/dev/null && pwd || true)"
for file in Dockerfile compose.yaml .dockerignore; do
    if [ -n "$here" ] && [ -f "$here/../deploy/pi/$file" ]; then
        cp "$here/../deploy/pi/$file" "$FORTE_DIR/$file"
    else
        curl -fsSL "$RAW/deploy/pi/$file" -o "$FORTE_DIR/$file" || fail "cannot download deploy/pi/$file from $RAW"
    fi
done

verify() {   # verify <file> <checksum file>
    expected="$(cut -d' ' -f1 "$2")"
    actual="$(sha256sum "$1" | cut -d' ' -f1)"
    [ "$expected" = "$actual" ] || fail "FORTE does not match its checksum"
    say "Checksum verified"
}
if [ -n "${FORTE_FILE:-}" ]; then
    say "Using $FORTE_FILE"
    cp "$FORTE_FILE" "$FORTE_DIR/forte.new"
elif [ -n "$here" ] && [ -f "$here/bin/forte-aarch64" ]; then
    say "Using the FORTE of this checkout"
    cp "$here/bin/forte-aarch64" "$FORTE_DIR/forte.new"
    [ ! -f "$here/bin/forte-aarch64.sha256" ] || verify "$FORTE_DIR/forte.new" "$here/bin/forte-aarch64.sha256"
else
    say "Downloading FORTE from $FORTE_URL"
    curl -fL --progress-bar "$FORTE_URL" -o "$FORTE_DIR/forte.new" || fail "cannot download FORTE from $FORTE_URL.
    Copy a binary here and set FORTE_FILE (build: runtime/build-modules.ps1 -Config pi/modules-pi)."
    if curl -fsSL "$FORTE_URL.sha256" -o "$FORTE_DIR/forte.sha256" 2>/dev/null; then
        verify "$FORTE_DIR/forte.new" "$FORTE_DIR/forte.sha256"
    fi
fi
chmod +x "$FORTE_DIR/forte.new"
mv "$FORTE_DIR/forte.new" "$FORTE_DIR/forte"

# --- container -------------------------------------------------------------------------------
say "Building and starting the container"
(cd "$FORTE_DIR" && $DOCKER compose up -d --build --force-recreate)

up=""
for _ in $(seq 1 40); do
    if (exec 3<>/dev/tcp/127.0.0.1/61499) 2>/dev/null; then up=1; break; fi
    sleep 0.5
done
[ -n "$up" ] || fail "FORTE does not answer on port 61499; see: cd $FORTE_DIR && $DOCKER compose logs"

address="$(hostname -I 2>/dev/null | cut -d' ' -f1)"
say "FORTE is running: this machine is an IEC 61499 PLC"
echo "  management  $address:61499"
echo "  OPC UA      opc.tcp://$address:4840"
echo "  GPIO        $gpiochip (the 40-pin header), chip 0 in a program"
echo "  container   cd $FORTE_DIR && docker compose ps | logs -f | restart | stop"
[ "$DOCKER" = docker ] || echo "  note        log out and in again to use docker without sudo"
if [ -n "$reboot_needed" ]; then
    echo "  note        reboot once for the PWM channels (sudo reboot); FORTE starts again by itself"
elif ! ls /sys/class/pwm/pwmchip* >/dev/null 2>&1; then
    echo "  note        no PWM channels (step pulses, motor speed, servo)"
fi
[ -s "$FORTE_DIR/boot/forte.fboot" ] || echo "  next        no program yet: install the tools and run 'modsync push <module> --target pi --host localhost'"
