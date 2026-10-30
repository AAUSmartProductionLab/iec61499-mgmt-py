param(
    # Reuse the exports already in .cache/modules (from an earlier build-modules.ps1): no modgen, no IDE.
    [switch]$SkipValidate,
    # Leave runtime/bin/forte-aarch64 as it is; the new FORTE is then only in the build folder.
    [switch]$NoPackage
)
# FORTE for the Raspberry Pi in one run, from the module projects as they are now:
#   1. modgen regenerates ModLib and the module projects from their specs,
#   2. the 4diac IDE exports their types as C++ into .cache/modules, which the FBE configuration
#      pi/modules-pi builds (FBE_EXTERNAL_MODULES_DIR),
#   3. the FBE cross-compiles FORTE 3.3.0 with the repository's patches for aarch64,
#   4. package-runtime.ps1 strips it into runtime/bin/forte-aarch64 with its checksum.
# See docs/forte-for-the-pi.md. Nothing is sent to a Pi.
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
Push-Location $repo
try {
    $build = @{ Config = 'pi/modules-pi' }
    if ($SkipValidate) { $build.SkipValidate = $true }
    & (Join-Path $PSScriptRoot 'build-modules.ps1') @build
    $forte = Join-Path $PSScriptRoot 'fbe\build\modules-pi\output\bin\forte'
    if (!(Test-Path -LiteralPath $forte)) { throw "$forte not found after the build" }
    if ($NoPackage) {
        "FORTE for the Pi: $forte"
        return
    }
    & (Join-Path $PSScriptRoot 'package-runtime.ps1') -Forte $forte
    # Changed against the last commit: the Pis need it, once it is committed.
    & git diff --quiet -- runtime/bin/forte-aarch64.sha256
    if ($LASTEXITCODE -eq 0) {
        'runtime/bin/forte-aarch64 is the same as the committed one: nothing to commit or install.'
    }
    else {
        'runtime/bin/forte-aarch64 changed. Next: commit it with its .sha256, then on the PC, with someone at the module,'
        '  python deploy/pi.py install                  (Filling; --spec cell/modules/stoppering.yaml for the other Pi)'
        '  python deploy/pi.py module'
    }
}
finally { Pop-Location }
