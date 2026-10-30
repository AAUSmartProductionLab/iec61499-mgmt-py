param(
    # 4diac FORTE Build Environment (https://github.com/eclipse-4diac/4diac-fbe); its
    # toolchain builds open62541, libmodbus etc. and links everything statically.
    [string]$Fbe = 'C:\4diac-fbe',
    # Config name (fbe/configurations/<name>.txt) or path below it (e.g. pi/modules-pi).
    [string]$Config = 'modules-win',
    # 4diac FORTE release built against; must match the IDE that exports the types.
    [string]$ForteTag = '3.3.0',
    # Only fetch and patch the FORTE source (build-project.ps1 compares exports against it).
    [switch]$FetchOnly
)
# Builds FORTE only, from the exports build-modules.ps1 validated and wrote.
$ErrorActionPreference = 'Stop'
$root = Join-Path $PSScriptRoot 'fbe'
# The FBE builds $root/4diac-forte when it exists (instead of its own bundled FORTE).
$forte = Join-Path $root '4diac-forte'
if (-not (Test-Path (Join-Path $forte 'CMakeLists.txt'))) {
    # git reports progress on stderr, which Windows PowerShell 5.1 turns into errors under 'Stop'.
    $ErrorActionPreference = 'Continue'
    & git -c advice.detachedHead=false clone -q --depth 1 --branch $ForteTag https://github.com/eclipse-4diac/4diac-forte.git $forte
    $ErrorActionPreference = 'Stop'
    if ($LASTEXITCODE -ne 0) { throw "Could not fetch 4diac FORTE $ForteTag" }
}
$have = (& git -C $forte describe --tags --exact-match 2>$null)
if ($have -ne $ForteTag) { throw "fbe/4diac-forte is at '$have', expected $ForteTag; delete it to re-fetch" }
# Fixes to the FORTE release (forte-patches/*.patch), applied in name order as a stack: a later
# patch may change what an earlier one added, so only the newest applied one still reverses
# cleanly. Found from the top down; the patches after it are applied.
$ErrorActionPreference = 'Continue'
$patches = @(Get-ChildItem -Path (Join-Path $PSScriptRoot 'forte-patches') -Filter '*.patch' | Sort-Object Name)
$applied = -1
for ($i = $patches.Count - 1; $i -ge 0; $i--) {
    & git -C $forte apply --reverse --check $patches[$i].FullName 2>$null
    if ($LASTEXITCODE -eq 0) { $applied = $i; break }
}
foreach ($patch in $patches[($applied + 1)..($patches.Count - 1)]) {
    if ($applied + 1 -ge $patches.Count) { break }
    & git -C $forte apply $patch.FullName
    if ($LASTEXITCODE -ne 0) { throw "Could not apply $($patch.Name) to fbe/4diac-forte" }
    "Applied $($patch.Name)"
}
$ErrorActionPreference = 'Stop'
if ($FetchOnly) { return }
Push-Location $root
try {
    # Out-of-tree FBE build: configurations/ and build/ live in $root. Call the shell script
    # directly; compile.cmd pauses on errors and then exits with 0.
    if (-not (Test-Path "$Fbe\toolchains\bin\sh.exe")) { & cmd.exe /c "`"$Fbe\toolchains\etc\install.cmd`"" }
    # The FBE hands its configuration's settings to CMake only when a build is configured from
    # scratch, and its own clean misses this out-of-tree build: a changed configuration starts
    # with a fresh CMake cache.
    $cache = Join-Path $root "build\$(Split-Path -Leaf $Config)\forte\build\CMakeCache.txt"
    $file = Join-Path $root "configurations\$Config.txt"
    if ((Test-Path $cache) -and (Get-Item $file).LastWriteTime -gt (Get-Item $cache).LastWriteTime) {
        Remove-Item $cache
        "Configuration $Config changed: CMake configures afresh"
    }
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
