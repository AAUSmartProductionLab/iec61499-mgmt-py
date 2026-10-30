param(
    # 4diac IDE 3.3 (this install was updated in place from 3.2.1); its export must match the
    # FORTE release in build-runtime.ps1 (-ForteTag). Elsewhere: set FORDIAC_IDE to 4diac-idec.exe.
    [string]$Ide = $(if ($env:FORDIAC_IDE) { $env:FORDIAC_IDE } else { 'C:\Users\marti\Downloads\4diac-ide_3.2.1-win32.win32.x86_64\4diac-ide\4diac-idec.exe' }),
    # 4diac project folder (its name is also the .sys name) and the export folder the FBE config
    # builds (FBE_EXTERNAL_MODULES_DIR).
    [Parameter(Mandatory)] [string]$ProjectDir,
    [Parameter(Mandatory)] [string]$Export,
    # modgen's type manifest: which types to compile and how many. Without one (a project made in
    # the IDE), every type is compiled except those FORTE has itself (fbe/4diac-forte).
    [string]$Manifest,
    # The exported CMake module; default: the name the export gives it (from MANIFEST.MF).
    [string]$Module,
    # CMake targets the exported module links to (e.g. forte-modlib: the library compiled once).
    [string[]]$Link = @()
)
$ErrorActionPreference = 'Stop'
$cache = Join-Path $PSScriptRoot '.cache'
$workspace = Join-Path $cache ('validation-' + [guid]::NewGuid().ToString('N'))
$export = $Export
$projectDir = (Resolve-Path -LiteralPath $ProjectDir).Path
$Project = Split-Path -Leaf $projectDir
$log = Join-Path $cache "validate-$Project.log"
$typeList = if ($Manifest) { Get-Content -Raw -LiteralPath $Manifest | ConvertFrom-Json } else { @() }
if (!(Test-Path -LiteralPath $Ide)) { throw "4diac IDE not found: $Ide (set FORDIAC_IDE or pass -Ide)" }
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
if (!$Manifest) {
    # A standard block copied into the project's Type Library: FORTE has a header at the same path.
    $forte = Join-Path $PSScriptRoot 'fbe\4diac-forte'
    if (!(Test-Path -LiteralPath $forte)) { throw "No FORTE source in $forte; run build-runtime.ps1 -FetchOnly" }
    # -Include does not filter together with -LiteralPath in Windows PowerShell 5.1.
    $typeHeader = { $_.Name -match '_(fbt|dtp)\.h$' }
    $own = @{}
    Get-ChildItem -LiteralPath $forte -Recurse -File | Where-Object $typeHeader |
        ForEach-Object { $own[($_.FullName -replace '^.*[\\/]include[\\/]forte[\\/]', '')] = $true }
    $headers = Join-Path $export 'include\forte'
    foreach ($header in Get-ChildItem -LiteralPath $headers -Recurse -File | Where-Object $typeHeader) {
        if ($own[$header.FullName.Substring($headers.Length + 1)]) {
            $short = $header.BaseName -replace '_(fbt|dtp)$', ''
            "FORTE has $short itself: not compiled again"
            $skip += $short
        }
    }
}
foreach ($short in $skip) {
    Get-ChildItem -LiteralPath $export -Recurse -File -Filter "$($short)_*" | Remove-Item -Force
    foreach ($list in Get-ChildItem -LiteralPath $export -Recurse -Filter 'CMakeLists.txt') {
        $lines = Get-Content -LiteralPath $list.FullName | Where-Object { $_ -notmatch "\b$($short)_(fbt|dtp)\.(cpp|h)\b" }
        Set-Content -LiteralPath $list.FullName -Value $lines -Encoding utf8
    }
}
# Header shims mapping the exporter's IO includes onto FORTE's modular IO (see forte-compat).
Copy-Item -Recurse -Force -Path (Join-Path $PSScriptRoot 'forte-compat\include\*') -Destination (Join-Path $export 'include')
if (!$Module) {
    $Module = (Select-String -LiteralPath (Join-Path $export 'CMakeLists.txt') -Pattern '^project\(forte-(\S+)').Matches[0].Groups[1].Value
}
# A project without MANIFEST.MF has no version, and CMake refuses the exported package without one.
$cmake = Join-Path $export 'CMakeLists.txt'
$text = Get-Content -Raw -LiteralPath $cmake
if ($text -notmatch 'project\([^)]*VERSION') {
    Set-Content -LiteralPath $cmake -Encoding utf8 -NoNewline -Value ($text -replace '(project\(forte-\S+)', "`$1`r`n        VERSION `"0.0.0`"")
}
# The exported module links only forte-core; composites also include standard FB headers.
Add-Content -LiteralPath (Join-Path $export 'CMakeLists.txt') -Encoding utf8 -Value @'

# Added by validate.ps1: headers of standard FBs used inside the composites (the IO blocks set up
# their GPIO line or PWM channel: the Linux modules, or their stand-ins elsewhere).
foreach (lib forte-events forte-net forte-gpiochip forte-pwmsysfs forte-iostubs)
        if (TARGET ${lib})
                target_link_libraries(forte-__MODULE__ PUBLIC ${lib})
        endif ()
endforeach ()
'@.Replace('__MODULE__', $Module)
foreach ($target in $Link) {
    Add-Content -LiteralPath (Join-Path $export 'CMakeLists.txt') -Encoding utf8 -Value "target_link_libraries(forte-$Module PUBLIC $target)"
}
$exported = @(Get-ChildItem -Path (Join-Path $export 'src') -Recurse -Include '*_fbt.cpp', '*_dtp.cpp')
$expected = if ($Manifest) { @($typeList | Where-Object { $_.exported }).Count } else { $exported.Count }
if ($exported.Count -ne $expected) { throw "Expected $expected exported types, got $($exported.Count)" }
# Keep the throwaway IDE workspace only when something failed (for its .metadata/.log).
Remove-Item -Recurse -Force -LiteralPath $workspace -ErrorAction SilentlyContinue
Write-Output "Validated system and exported all $expected types: $export"
