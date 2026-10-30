param(
    # Where the kit's folder and zip go (runtime/dist is not tracked).
    [string]$Out = (Join-Path $PSScriptRoot 'dist'),
    # Leave out the lab's exported modules (ModLib, Filling, Stoppering, Filler); a FORTE built from the
    # kit then cannot run the lab's module programs.
    [switch]$NoLabModules
)
# A kit for building FORTE with one's own block types without this repository: the build scripts,
# FBE configurations, FORTE patches and the lab's exported modules (from the last build-modules.ps1),
# with kit/README.md. It builds the same FORTE as runtime/bin/forte-aarch64 plus the new types.
$ErrorActionPreference = 'Stop'
$kit = Join-Path $Out 'forte-kit'
if (Test-Path -LiteralPath $kit) { Remove-Item -Recurse -Force -LiteralPath $kit }
New-Item -ItemType Directory -Force -Path $kit | Out-Null
$files = 'build-project.ps1', 'build-runtime.ps1', 'validate.ps1', 'validate.xml', 'check-project.ps1',
         'package-runtime.ps1', 'install.sh'
foreach ($file in $files) { Copy-Item -LiteralPath (Join-Path $PSScriptRoot $file) -Destination $kit }
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'kit\README.md') -Destination $kit
foreach ($dir in 'forte-patches', 'forte-compat', 'fbe\configurations', 'fbe\dependencies') {
    $to = Join-Path $kit $dir
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $to) | Out-Null
    Copy-Item -Recurse -LiteralPath (Join-Path $PSScriptRoot $dir) -Destination $to
}
if (!$NoLabModules) {
    $modules = Join-Path $PSScriptRoot '.cache\modules'
    if (!(Test-Path -LiteralPath (Join-Path $modules 'modlib'))) { throw "No exports in $modules; run build-modules.ps1 first" }
    New-Item -ItemType Directory -Force -Path (Join-Path $kit '.cache') | Out-Null
    Copy-Item -Recurse -LiteralPath $modules -Destination (Join-Path $kit '.cache\modules')
}
$zip = Join-Path $Out 'forte-kit.zip'
if (Test-Path -LiteralPath $zip) { Remove-Item -Force -LiteralPath $zip }
# Entry by entry: Windows PowerShell 5.1 (Compress-Archive, ZipFile) writes \ into the paths, which
# unzip outside Windows keeps in the file names.
Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [IO.Compression.ZipFile]::Open($zip, 'Create')
try {
    foreach ($file in Get-ChildItem -LiteralPath $kit -Recurse -File -Force) {
        $entry = 'forte-kit/' + $file.FullName.Substring($kit.Length + 1).Replace('\', '/')
        [void][IO.Compression.ZipFileExtensions]::CreateEntryFromFile($archive, $file.FullName, $entry, 'Optimal')
    }
}
finally { $archive.Dispose() }
"Kit: $kit"
"Zip: $zip ({0:N1} MB)" -f ((Get-Item -LiteralPath $zip).Length / 1MB)
