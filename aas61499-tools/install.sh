#!/usr/bin/env bash
# Install the IEC 61499 tools: modsync (read what runs on a module, compare it with its spec,
# describe it as an AAS, push changes and rewire it online), modgen (module spec -> 4diac
# project) and iec61499 (management commands, boot files).
#
#   curl -fsSL https://raw.githubusercontent.com/AAUSmartProductionLab/iec61499-mgmt-py/main/aas61499-tools/install.sh | bash
#
# It clones the repository (the tools read the module specs in it), makes a Python environment
# inside it and links the commands into ~/.local/bin. Run the script again to update.
#
#   modsync pull --host localhost                         # which module runs here, drift from its spec, its AAS
#   modsync push filling --target pi --host localhost     # bring this module to its spec (cell/modules/filling.yaml)
#   modsync push filling --target pi --host localhost --dry-run    # only show what would change
#   modsync watch                                         # report whenever a module comes online or changes
#
# Settings (environment variables):
#   IEC61499_HOME  where the repository goes (default ~/iec61499-aas-reconfig)
#   REF            branch or tag (default main)
#   REPO_URL       clone from here instead of GitHub
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/AAUSmartProductionLab/iec61499-mgmt-py.git}"
REF="${REF:-main}"
HOME_DIR="${IEC61499_HOME:-$HOME/iec61499-aas-reconfig}"
BIN="$HOME/.local/bin"

say() { printf '\033[1m==> %s\033[0m\n' "$*"; }
fail() { printf 'install: %s\n' "$*" >&2; exit 1; }

command -v git >/dev/null || fail "git is missing (sudo apt install git)"
command -v python3 >/dev/null || fail "python3 is missing (sudo apt install python3 python3-venv)"
python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))' || fail "Python 3.11 or newer is needed; this is $(python3 -V)"
python3 -c 'import venv, ensurepip' 2>/dev/null || fail "Python's venv module is missing (sudo apt install python3-venv)"

if [ -d "$HOME_DIR/.git" ]; then
    say "Updating $HOME_DIR ($REF)"
    git -C "$HOME_DIR" fetch --quiet --tags origin
    git -C "$HOME_DIR" checkout --quiet "$REF"
    git -C "$HOME_DIR" pull --quiet --ff-only origin "$REF" 2>/dev/null || true      # a tag has nothing to pull
else
    say "Cloning into $HOME_DIR ($REF)"
    git clone --quiet --branch "$REF" "$REPO_URL" "$HOME_DIR"
fi

say "Installing the Python packages"
[ -x "$HOME_DIR/.venv/bin/python" ] || python3 -m venv "$HOME_DIR/.venv"
"$HOME_DIR/.venv/bin/python" -m pip install --quiet --upgrade pip
"$HOME_DIR/.venv/bin/python" -m pip install --quiet -e "$HOME_DIR[aas,opcua]"

mkdir -p "$BIN"
for tool in modsync modgen iec61499; do
    ln -sf "$HOME_DIR/.venv/bin/$tool" "$BIN/$tool"
done

say "Installed: modsync, modgen, iec61499 (in $BIN)"
case ":$PATH:" in
    *":$BIN:"*) ;;
    *) echo "  note  $BIN is not on your PATH; add it:  echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.profile  (then log in again)";;
esac
echo "  specs $HOME_DIR/cell/modules/"
echo "  try   modsync pull --host localhost"
