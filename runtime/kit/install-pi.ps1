param(
    # The Pi's login and address, e.g. pi@192.168.0.42 (SSH must be enabled on the Pi).
    [Parameter(Mandatory)] [string]$Pi,
    # Folder on the Pi the kit's files are copied to.
    [string]$Folder = 'forte-kit'
)
# Put this kit's FORTE on a Raspberry Pi over SSH, without the internet: install.sh, bin/forte-aarch64
# with its checksum, the container files (pi/) and the base images (images/) are copied with scp,
# then install.sh runs on the Pi (it asks for the sudo password there). Windows has ssh and scp
# (OpenSSH client); each asks for the Pi's password unless a key is set up.
$ErrorActionPreference = 'Stop'
$binary = Join-Path $PSScriptRoot 'bin\forte-aarch64'
if (!(Test-Path -LiteralPath $binary)) { throw "$binary not found; build it first with build-project.ps1" }
foreach ($tool in 'ssh', 'scp') {
    if (!(Get-Command $tool -ErrorAction SilentlyContinue)) { throw "$tool not found: add the Windows feature 'OpenSSH Client'" }
}
# Native programs' stderr must not stop Windows PowerShell 5.1; success is their exit code.
$ErrorActionPreference = 'Continue'
function Run([string]$what) {
    if ($LASTEXITCODE -ne 0) { throw "$what failed (exit $LASTEXITCODE)" }
}
"Copying the kit to ${Pi}:$Folder"
& ssh $Pi "mkdir -p $Folder/bin $Folder/pi $Folder/images"; Run 'ssh'
& scp -q (Join-Path $PSScriptRoot 'install.sh') "${Pi}:$Folder/"; Run 'scp install.sh'
& scp -q $binary "$binary.sha256" "${Pi}:$Folder/bin/"; Run 'scp bin'
$container = @(Get-ChildItem -LiteralPath (Join-Path $PSScriptRoot 'pi') -File -Force | ForEach-Object FullName)
& scp -q @container "${Pi}:$Folder/pi/"; Run 'scp pi'
$images = @(Get-ChildItem -LiteralPath (Join-Path $PSScriptRoot 'images') -Filter '*.tar' -File -ErrorAction SilentlyContinue | ForEach-Object FullName)
if ($images) { & scp -q @images "${Pi}:$Folder/images/"; Run 'scp images' }
"Installing on the Pi"
& ssh -t $Pi "bash $Folder/install.sh"; Run 'install.sh'
