param(
    # 4diac IDE 3.3 (this install was updated in place from 3.2.1); its export must match the
    # FORTE release in build-runtime.ps1 (-ForteTag).
    [string]$Ide = 'C:\Users\marti\Downloads\4diac-ide_3.2.1-win32.win32.x86_64\4diac-ide\4diac-idec.exe',
    # 4diac project folder under 4diac/ (also its .sys name), its type manifest, the export
    # folder the FBE config builds (FBE_EXTERNAL_MODULES_DIR) and the exported CMake module.
    [string]$Project = 'FillingCellFixed',
    [string]$Manifest = (Join-Path $PSScriptRoot 'types-manifest.json'),
    [string]$Export = (Join-Path $PSScriptRoot '.cache\export'),
    [string]$Module = 'fillingcell',
    # CMake targets the exported module links to (e.g. forte-modlib: the library compiled once).
    [string[]]$Link = @()
)
$ErrorActionPreference = 'Stop'
$cache = Join-Path $PSScriptRoot '.cache'
$workspace = Join-Path $cache ('validation-' + [guid]::NewGuid().ToString('N'))
$export = $Export
$projectDir = Join-Path (Split-Path $PSScriptRoot) $Project
$log = Join-Path $cache "validate-$Project.log"
$typeList = Get-Content -Raw -LiteralPath $Manifest | ConvertFrom-Json
New-Item -ItemType Directory -Force -Path $cache | Out-Null
if (Test-Path -LiteralPath $export) { Remove-Item -Recurse -Force -LiteralPath $export }
# Windows PowerShell 5.1 turns a native program's stderr into terminating errors under 'Stop';
# the IDE logs to stderr, so success is judged by the exit code and the ant log instead.
$ErrorActionPreference = 'Continue'
& $Ide -nosplash --launcher.suppressErrors -application org.eclipse.ant.core.antRunner `
    -data $workspace -buildfile (Join-Path $PSScriptRoot 'validate.xml') `
    "-Dproject.path=$projectDir" "-Dproject.name=$Project" "-Dexport.path=$export" `
    -vmargs -Djava.awt.headless=true *> $log
$result = $LASTEXITCODE
$ErrorActionPreference = 'Stop'
Get-Content -LiteralPath $log -Tail 25
$eclipseLog = Join-Path $workspace '.metadata/.log'
if (Test-Path -LiteralPath $eclipseLog) {
    $loadErrors = Select-String -LiteralPath $eclipseLog -Pattern 'Error loading type|Application error|Error during template generation'
    if ($loadErrors) { throw "IDE loading/export errors: $eclipseLog" }
}
if ($result -ne 0 -or !(Select-String -LiteralPath $log -Pattern '^BUILD SUCCESSFUL')) {
    throw "4diac validation failed; see $log"
}
# Generic comm FB declarations (e.g. SERVER_2_5) exist only so the IDE knows their interface;
# FORTE instantiates them from GEN_SERVER, so their generated C++ must not be compiled.
# The exporter emits generic comm FBs under their generic class name (GEN_SERVER etc.).
$skip = @($typeList | Where-Object { -not $_.exported } | ForEach-Object { ($_.type -split '::')[-1] })
$skip += @('GEN_SERVER', 'GEN_CLIENT', 'GEN_PUBLISH', 'GEN_SUBSCRIBE')
foreach ($short in $skip) {
    Get-ChildItem -LiteralPath $export -Recurse -File -Filter "$($short)_*" | Remove-Item -Force
    foreach ($list in Get-ChildItem -LiteralPath $export -Recurse -Filter 'CMakeLists.txt') {
        $lines = Get-Content -LiteralPath $list.FullName | Where-Object { $_ -notmatch "\b$($short)_(fbt|dtp)\.(cpp|h)\b" }
        Set-Content -LiteralPath $list.FullName -Value $lines -Encoding utf8
    }
}
# Header shims mapping the exporter's IO includes onto FORTE's modular IO (see forte-compat).
Copy-Item -Recurse -Force -Path (Join-Path $PSScriptRoot 'forte-compat\include\*') -Destination (Join-Path $export 'include')
# The exported module links only forte-core; composites also include standard FB headers.
Add-Content -LiteralPath (Join-Path $export 'CMakeLists.txt') -Encoding utf8 -Value @'

# Added by validate.ps1: headers of standard FBs used inside the composites.
foreach (lib forte-events forte-net)
        if (TARGET ${lib})
                target_link_libraries(forte-__MODULE__ PUBLIC ${lib})
        endif ()
endforeach ()
'@.Replace('__MODULE__', $Module)
foreach ($target in $Link) {
    Add-Content -LiteralPath (Join-Path $export 'CMakeLists.txt') -Encoding utf8 -Value "target_link_libraries(forte-$Module PUBLIC $target)"
}
$expected = @($typeList | Where-Object { $_.exported }).Count
$exported = @(Get-ChildItem -Path (Join-Path $export 'src') -Recurse -Include '*_fbt.cpp', '*_dtp.cpp')
if ($exported.Count -ne $expected) { throw "Expected $expected exported types, got $($exported.Count)" }
# Keep the throwaway IDE workspace only when something failed (for its .metadata/.log).
Remove-Item -Recurse -Force -LiteralPath $workspace -ErrorAction SilentlyContinue
Write-Output "Validated system and exported all $expected types: $export"
