#!/usr/bin/env bash
# Set up a module's Raspberry Pi in one go: the tools, the runtime, and the module's program.
#
#   curl -fsSL https://raw.githubusercontent.com/AAUSmartProductionLab/iec61499-mgmt-py/main/deploy/install.sh | bash -s -- filling
#   curl -fsSL https://raw.githubusercontent.com/AAUSmartProductionLab/iec61499-mgmt-py/main/deploy/install.sh | bash          # no program
#
# The argument names a module spec (cell/modules/<name>.yaml); its "pi" target is deployed.
# Without it, FORTE starts with whatever program it had (none after a first install).
# The steps are the two other installers, which also run on their own:
#   aas61499-tools/install.sh   the tools (modsync, modgen, iec61499)
#   runtime/install.sh          FORTE in Docker
# Their settings (REF, IEC61499_HOME, FORTE_FILE, FORTE_URL, FORTE_DIR) apply here too.
set -euo pipefail

MODULE="${1:-}"
TARGET="${TARGET:-pi}"
REPO="${REPO:-AAUSmartProductionLab/iec61499-mgmt-py}"
REF="${REF:-main}"
HOME_DIR="${IEC61499_HOME:-$HOME/iec61499-aas-reconfig}"
export REF

say() { printf '\033[1m==> %s\033[0m\n' "$*"; }
fail() { printf 'install: %s\n' "$*" >&2; exit 1; }

# The tools first: they bring the repository, which holds the other installer and the specs.
here="$(cd "$(dirname "${BASH_SOURCE[0]:-/nonexistent/x}")" 2>/dev/null && pwd || true)"
if [ -n "$here" ] && [ -f "$here/../aas61499-tools/install.sh" ]; then
    bash "$here/../aas61499-tools/install.sh"
else
    command -v curl >/dev/null || fail "curl is missing (sudo apt install curl)"
    curl -fsSL "https://raw.githubusercontent.com/$REPO/$REF/aas61499-tools/install.sh" | bash
fi
bash "$HOME_DIR/runtime/install.sh"

if [ -n "$MODULE" ]; then
    spec="$HOME_DIR/cell/modules/$MODULE.yaml"
    [ -f "$spec" ] || fail "no module spec $spec (have: $(cd "$HOME_DIR/cell/modules" && ls *.yaml | sed 's/\.yaml$//' | tr '\n' ' '))"
    say "Deploying the $MODULE module (target $TARGET)"
    "$HOME/.local/bin/modsync" push "$MODULE" --target "$TARGET" --host localhost
fi

say "Done"
echo "  state   modsync pull --host localhost"
echo "  change  edit $HOME_DIR/cell/modules/<module>.yaml, then: modsync push <module> --target $TARGET --host localhost"
