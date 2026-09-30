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
$root = Split-Path (Split-Path $PSScriptRoot)
$exports = Join-Path $PSScriptRoot '.cache\modules'
if (-not $SkipValidate) {
    & python -m modgen
    if ($LASTEXITCODE -ne 0) { throw 'modgen failed' }
    if (Test-Path -LiteralPath $exports) { Remove-Item -Recurse -Force -LiteralPath $exports }
    New-Item -ItemType Directory -Force -Path $exports | Out-Null
    $projects = @(@{Project = 'ModLib'; Module = 'modlib'; Link = @()})
    foreach ($spec in Get-ChildItem -Path (Join-Path $root 'modules') -Filter '*.yaml' | Sort-Object Name) {
        $info = & python -c "import sys, modgen; s = modgen.load(sys.argv[1]); print(s.project, s.package)" $spec.FullName
        $project, $package = $info -split ' '
        $projects += @{Project = $project; Module = $package; Link = @('forte-modlib')}
    }
    foreach ($p in $projects) {
        & (Join-Path $PSScriptRoot 'validate.ps1') -Project $p.Project -Module $p.Module -Link $p.Link `
            -Manifest (Join-Path $PSScriptRoot "manifests\$($p.Project).json") -Export (Join-Path $exports $p.Module)
    }
}
& (Join-Path $PSScriptRoot 'build-runtime.ps1') -SkipValidate -Config $Config
