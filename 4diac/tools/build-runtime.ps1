param(
    # 4diac FORTE Build Environment (https://github.com/eclipse-4diac/4diac-fbe); its
    # toolchain builds open62541, libmodbus etc. and links everything statically.
    [string]$Fbe = 'C:\4diac-fbe',
    # Config name (fbe/configurations/<name>.txt) or directory (e.g. configurations/pi).
    [string]$Config = 'fillingcell-win',
    # 4diac FORTE release built against; must match the IDE that exports the types.
    [string]$ForteTag = '3.3.0',
    [switch]$SkipValidate,
    # Passed to validate.ps1: 4diac project, type manifest, export folder and CMake module.
    [string]$Project = 'FillingCellFixed',
    [string]$Manifest = (Join-Path $PSScriptRoot 'types-manifest.json'),
    [string]$Export = (Join-Path $PSScriptRoot '.cache\export'),
    [string]$Module = 'fillingcell'
)
$ErrorActionPreference = 'Stop'
if (-not $SkipValidate) {
    & (Join-Path $PSScriptRoot 'validate.ps1') -Project $Project -Manifest $Manifest -Export $Export -Module $Module
}
$root = Join-Path $PSScriptRoot 'fbe'
# The FBE builds $root/4diac-forte when it exists (instead of its own bundled FORTE).
$forte = Join-Path $root '4diac-forte'
if (-not (Test-Path (Join-Path $forte 'CMakeLists.txt'))) {
    & git clone --depth 1 --branch $ForteTag https://github.com/eclipse-4diac/4diac-forte.git $forte
    if ($LASTEXITCODE -ne 0) { throw "Could not fetch 4diac FORTE $ForteTag" }
}
$have = (& git -C $forte describe --tags --exact-match 2>$null)
if ($have -ne $ForteTag) { throw "fbe/4diac-forte is at '$have', expected $ForteTag; delete it to re-fetch" }
# Fixes to the FORTE release (forte-patches/*.patch, in name order); a patch already applied is skipped.
$ErrorActionPreference = 'Continue'
foreach ($patch in Get-ChildItem -Path (Join-Path $PSScriptRoot 'forte-patches') -Filter '*.patch' | Sort-Object Name) {
    & git -C $forte apply --reverse --check $patch.FullName 2>$null
    if ($LASTEXITCODE -eq 0) { continue }
    & git -C $forte apply $patch.FullName
    if ($LASTEXITCODE -ne 0) { throw "Could not apply $($patch.Name) to fbe/4diac-forte" }
    "Applied $($patch.Name)"
}
$ErrorActionPreference = 'Stop'
Push-Location $root
try {
    # Out-of-tree FBE build: configurations/ and build/ live in $root. Call the shell script
    # directly; compile.cmd pauses on errors and then exits with 0.
    if (-not (Test-Path "$Fbe\toolchains\bin\sh.exe")) { & cmd.exe /c "`"$Fbe\toolchains\etc\install.cmd`"" }
    # See validate.ps1: native stderr must not abort Windows PowerShell 5.1.
    $ErrorActionPreference = 'Continue'
    & "$Fbe\toolchains\bin\sh.exe" "$Fbe\scripts\compile.sh" $Config
    $built = $LASTEXITCODE
    $ErrorActionPreference = 'Stop'
    if ($built -ne 0) { throw "FBE build failed; see $root\build\<config>\forte.log" }
}
finally { Pop-Location }
Get-ChildItem -Path (Join-Path $root 'build') -Recurse -Include 'forte.exe', 'forte' -File |
    Where-Object { $_.DirectoryName -like '*output*bin*' } | ForEach-Object { "Runtime: $($_.FullName)" }
