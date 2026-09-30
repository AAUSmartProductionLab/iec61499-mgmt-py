param(
    # FBE configuration: modules-win (this PC) or pi/modules-pi (Raspberry Pi, aarch64).
    [string]$Config = 'modules-win',
    # Only rebuild FORTE from the existing exports.
    [switch]$SkipValidate
)
# One FORTE with every module: the library (ModLib, package modlib) is exported once and each
# module's export links to it; the FBE builds all folders below .cache/modules
# (FBE_EXTERNAL_MODULES_DIR in configurations/modules-win.txt and pi/modules-pi.txt).
$ErrorActionPreference = 'Stop'
$exports = Join-Path $PSScriptRoot '.cache\modules'
if (-not $SkipValidate) {
    & python -m modgen
    if ($LASTEXITCODE -ne 0) { throw 'modgen failed' }
    if (Test-Path -LiteralPath $exports) { Remove-Item -Recurse -Force -LiteralPath $exports }
    New-Item -ItemType Directory -Force -Path $exports | Out-Null
    # Project folder, manifest and package of ModLib and of every module (from modgen).
    $listing = & python -m modgen --list
    if ($LASTEXITCODE -ne 0) { throw 'modgen --list failed' }
    foreach ($line in $listing) {
        $project, $dir, $manifest, $package = $line -split '\|'
        $link = if ($project -eq 'ModLib') { @() } else { @('forte-modlib') }
        & (Join-Path $PSScriptRoot 'validate.ps1') -ProjectDir $dir -Module $package -Link $link `
            -Manifest $manifest -Export (Join-Path $exports $package)
    }
}
& (Join-Path $PSScriptRoot 'build-runtime.ps1') -Config $Config
