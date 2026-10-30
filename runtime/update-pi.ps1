param(
    # The Pi's login and address, e.g. pi@192.168.0.42. It already runs FORTE in Docker from ~/forte
    # (runtime/install.sh or install-pi.ps1 did that once).
    [Parameter(Mandatory)] [string]$Pi,
    # 4diac project folders whose block types go into FORTE (as for build-project.ps1).
    [string[]]$Project,
    # The 4diac IDE (4diac-idec.exe); default: FORDIAC_IDE.
    [string]$Ide,
    # Send bin/forte-aarch64 as it is, without building.
    [switch]$SkipBuild,
    # FORTE's folder on the Pi, below the login's home.
    [string]$Folder = 'forte',
    # Do not ask before FORTE restarts on the Pi.
    [switch]$Force
)
# Build FORTE with a project's block types and put it on a Pi that already runs FORTE:
#   1. build-project.ps1: export the project, cross-compile, bin/forte-aarch64,
#   2. scp the binary to the Pi, next to the one that runs,
#   3. on the Pi: check its checksum, keep the old one as forte.old, put the new one in place,
#      rebuild the image and recreate the container (the image copies the binary in when it is
#      built, so a restart alone would keep the old one),
#   4. wait until FORTE says it is up and running, and show the end of its log.
# Two connections to the Pi (scp, ssh): each asks for the password unless an SSH key is set up.
# The program on the Pi (boot/forte.fboot) is kept and starts again.
$ErrorActionPreference = 'Stop'
if (!$SkipBuild -and !$Project) { throw 'Give -Project <4diac project folder>, or -SkipBuild to send bin/forte-aarch64 as it is' }
foreach ($tool in 'ssh', 'scp') {
    if (!(Get-Command $tool -ErrorAction SilentlyContinue)) { throw "$tool not found: add the Windows feature 'OpenSSH Client'" }
}
# Asked first, so nobody has to wait through the build for it.
if (!$Force) {
    $answer = Read-Host "FORTE on $Pi will restart and run its program again; on a module it may move an axis. Go on? [y/N]"
    if ($answer -notmatch '^(y|yes)$') { 'Nothing done.'; return }
}
if (!$SkipBuild) {
    $build = @{ Project = $Project }
    if ($Ide) { $build.Ide = $Ide }
    & (Join-Path $PSScriptRoot 'build-project.ps1') @build
}
$binary = Join-Path $PSScriptRoot 'bin\forte-aarch64'
if (!(Test-Path -LiteralPath $binary)) { throw "$binary not found; build it first" }
$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $binary).Hash.ToLower()

# Native programs' stderr must not stop Windows PowerShell 5.1; success is their exit code.
$ErrorActionPreference = 'Continue'
"Sending FORTE to ${Pi}:$Folder"
& scp -q $binary "${Pi}:$Folder/forte.new"
if ($LASTEXITCODE -ne 0) { throw "scp to $Pi failed (exit $LASTEXITCODE): is $Folder there?" }
# One line for the Pi's shell; only single quotes inside, which pass through to ssh unchanged.
$ready = 'FORTE is up and running'
$remote = @(
    "cd $Folder || exit 2",
    "echo '$hash  forte.new' | sha256sum -c --quiet || exit 3",
    '{ [ ! -f forte ] || mv -f forte forte.old; } && mv forte.new forte',
    'if docker info >/dev/null 2>&1; then D=docker; else D=''sudo docker''; fi',
    'echo Rebuilding the image and starting FORTE',
    '$D compose up -d --build --force-recreate forte || exit 4',
    "for i in `$(seq 1 30); do `$D compose logs forte 2>&1 | grep -q '$ready' && break; sleep 1; done",
    '$D compose logs --tail 15 forte',
    "`$D compose logs forte 2>&1 | grep -q '$ready' || exit 5"
) -join '; '
& ssh -t $Pi $remote
$code = $LASTEXITCODE
$ErrorActionPreference = 'Stop'
switch ($code) {
    0 { "FORTE runs the new build on $Pi (the old one is ~/$Folder/forte.old)." }
    2 { throw "No folder ~/$Folder on the Pi: install FORTE there first (install-pi.ps1)" }
    3 { throw 'The binary on the Pi does not match its checksum; nothing was replaced. Run again.' }
    4 { throw "docker compose failed on the Pi; see: ssh $Pi `"cd $Folder && docker compose logs forte`"" }
    5 { throw "FORTE did not report '$ready' within 30 s; its log is above. Back to the old one: ssh $Pi `"cd $Folder && mv forte.old forte && docker compose up -d --build --force-recreate forte`"" }
    default { throw "ssh to $Pi failed (exit $code)" }
}
