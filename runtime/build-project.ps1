param(
    # 4diac IDE project folders whose block types go into FORTE (each with its <name>.sys).
    [Parameter(Mandatory)] [string[]]$Project,
    # FBE configuration: pi/modules-pi (Raspberry Pi, aarch64) or modules-win (this PC).
    [string]$Config = 'pi/modules-pi',
    # The 4diac IDE 3.3 (4diac-idec.exe); default: FORDIAC_IDE, else validate.ps1's.
    [string]$Ide,
    # Compile only these projects' types, not the other exports in .cache/modules (the lab's modules).
    [switch]$Alone,
    # Leave bin/forte-aarch64 as it is; the new FORTE is then only in the build folder.
    [switch]$NoPackage
)
# FORTE with the block types of any 4diac project, made in the IDE (no modgen, no type manifest):
# each project is exported into .cache/modules/<project> next to what is there already, and the FBE
# compiles them all. For the Pi the result is packaged into bin/forte-aarch64. See
# docs/forte-for-the-pi.md (in the kit: README.md).
$ErrorActionPreference = 'Stop'
$exports = Join-Path $PSScriptRoot '.cache\modules'
New-Item -ItemType Directory -Force -Path $exports | Out-Null
if ($Alone) { Get-ChildItem -LiteralPath $exports -Directory | Remove-Item -Recurse -Force }
& (Join-Path $PSScriptRoot 'build-runtime.ps1') -FetchOnly
foreach ($dir in $Project) {
    $dir = (Resolve-Path -LiteralPath $dir).Path
    $name = Split-Path -Leaf $dir
    if (!(Test-Path -LiteralPath (Join-Path $dir "$name.sys"))) { throw "$dir has no $name.sys: is it a 4diac project folder?" }
    $export = Join-Path $exports $name.ToLower()
    # Every module is linked to the lab's library when it is there: its types may use ModLib's.
    $link = if (Test-Path -LiteralPath (Join-Path $exports 'modlib')) { @('forte-modlib') } else { @() }
    $validate = @{ ProjectDir = $dir; Export = $export; Link = $link }
    if ($Ide) { $validate.Ide = $Ide }
    & (Join-Path $PSScriptRoot 'validate.ps1') @validate
}
& (Join-Path $PSScriptRoot 'build-runtime.ps1') -Config $Config
if ($Config -notlike 'pi/*' -or $NoPackage) { return }
& (Join-Path $PSScriptRoot 'package-runtime.ps1') -Forte (Join-Path $PSScriptRoot 'fbe\build\modules-pi\output\bin\forte')
