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
    # A boot file made in the IDE (right-click the device, Create FORTE Boot-Files): it becomes the
    # Pi's program (boot/forte.fboot, the one before goes to boot/forte.fboot.old) and FORTE starts
    # with it. Instead of a deployment from the IDE, which deletes the running program first.
    [string]$Program,
    # Start FORTE without the program on the Pi: boot/forte.fboot is moved to boot/forte.fboot.old,
    # and FORTE waits for a deployment from the IDE.
    [switch]$NoProgram,
    # FORTE's folder on the Pi, below the login's home.
    [string]$Folder = 'forte',
    # Do not ask before FORTE restarts on the Pi.
    [switch]$Force
)
# Put FORTE, its program or both on a Pi that already runs FORTE:
#   1. build-project.ps1 (with -Project): export the project, cross-compile, bin/forte-aarch64,
#   2. scp the binary and the boot file (-Program) to the Pi, next to the ones that run,
#   3. on the Pi: check their checksums, keep the old ones (forte.old, boot/forte.fboot.old), put the
#      new ones in place, stop FORTE, wait until its port is free, rebuild the image (a new binary:
#      the image copies it in when it is built) and start a new container,
#   4. wait until FORTE says it is up and running, show the end of its log, check that the program
#      loaded and that FORTE answers on its port.
# Two connections to the Pi (scp, ssh): each asks for the password unless an SSH key is set up.
# Without -Program the program on the Pi (boot/forte.fboot) is kept and starts again, unless
# -NoProgram. The IDE never writes that file: a deployment from it is gone when FORTE restarts.
$ErrorActionPreference = 'Stop'
$binary = $SkipBuild -or $Project
if (!$binary -and !$Program) { throw 'Give -Project <4diac project folder>, -SkipBuild to send bin/forte-aarch64 as it is, or -Program <boot file>' }
if ($SkipBuild -and $Project) { throw '-SkipBuild sends the last build (bin/forte-aarch64) and does not read -Project: give one of them' }
if ($Program -and $NoProgram) { throw '-Program and -NoProgram: give one of them' }
if ($Program) {
    if (!(Test-Path -LiteralPath $Program -PathType Leaf)) { throw "No boot file $Program" }
    # Each line a destination and a request: 'RES;<Request ...>', or ';<Request ...>' for the device.
    $lines = @(Get-Content -LiteralPath $Program | Where-Object { $_.Trim() })
    $bad = @($lines | Where-Object { $_ -notmatch '^[^;<]*;\s*<Request\b' })
    if (!$lines -or $bad) { throw "$Program is not a FORTE boot file (made in the IDE: right-click the device, Create FORTE Boot-Files)" }
}
foreach ($tool in 'ssh', 'scp') {
    if (!(Get-Command $tool -ErrorAction SilentlyContinue)) { throw "$tool not found: add the Windows feature 'OpenSSH Client'" }
}
# Asked first, so nobody has to wait through the build for it.
if (!$Force) {
    $question = if ($Program) { "FORTE on $Pi will restart with the program in $(Split-Path -Leaf $Program); on a module it may move an axis." }
                elseif ($NoProgram) { "FORTE on $Pi will restart without a program (the one there goes to boot/forte.fboot.old)." }
                else { "FORTE on $Pi will restart and run the program it has (boot/forte.fboot) again; on a module it may move an axis." }
    $answer = Read-Host "$question Go on? [y/N]"
    if ($answer -notmatch '^(y|yes)$') { 'Nothing done.'; return }
}
if ($Project) {
    $build = @{ Project = $Project }
    if ($Ide) { $build.Ide = $Ide }
    & (Join-Path $PSScriptRoot 'build-project.ps1') @build
}
# What goes to the Pi, under the names it gets there, so that one scp sends both.
$outgoing = Join-Path ([IO.Path]::GetTempPath()) ('forte-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $outgoing | Out-Null
$files = @()
if ($binary) {
    $built = Join-Path $PSScriptRoot 'bin\forte-aarch64'
    if (!(Test-Path -LiteralPath $built)) { throw "$built not found; build it first" }
    Copy-Item -LiteralPath $built -Destination (Join-Path $outgoing 'forte.new')
    $files += Join-Path $outgoing 'forte.new'
}
if ($Program) {
    # Unix line ends: FORTE reads the file on Linux.
    [IO.File]::WriteAllText((Join-Path $outgoing 'forte.fboot.new'), (($lines -join "`n") + "`n"))
    $files += Join-Path $outgoing 'forte.fboot.new'
}
$sums = @{}
foreach ($file in $files) { $sums[(Split-Path -Leaf $file)] = (Get-FileHash -Algorithm SHA256 -LiteralPath $file).Hash.ToLower() }

# Native programs' stderr must not stop Windows PowerShell 5.1; success is their exit code.
$ErrorActionPreference = 'Continue'
"Sending $((@($(if ($binary) { 'FORTE' }), $(if ($Program) { 'the program' })) | Where-Object { $_ }) -join ' and ') to ${Pi}:$Folder"
& scp -q @files "${Pi}:$Folder/"
$sent = $LASTEXITCODE
Remove-Item -Recurse -Force -LiteralPath $outgoing
if ($sent -ne 0) { throw "scp to $Pi failed (exit $sent): is $Folder there?" }
# One line for the Pi's shell; only single quotes inside, which pass through to ssh unchanged.
$ready = 'FORTE is up and running'
$remote = @("cd $Folder || exit 2")
foreach ($name in $sums.Keys) { $remote += "echo '$($sums[$name])  $name' | sha256sum -c --quiet || exit 3" }
if ($binary) {
    # scp from Windows drops the execute bit, and the image keeps the file's mode.
    $remote += 'chmod +x forte.new', '{ [ ! -f forte ] || mv -f forte forte.old; } && mv forte.new forte'
}
# The program before, unless empty, is kept as boot/forte.fboot.old.
$keep = '{ [ ! -s boot/forte.fboot ] || { mv -f boot/forte.fboot boot/forte.fboot.old && echo The program before is kept as boot/forte.fboot.old; }; }'
if ($Program) { $remote += "$keep && mv forte.fboot.new boot/forte.fboot" }
if ($NoProgram) { $remote += "$keep && : > boot/forte.fboot" }
$remote += @(
    'if docker info >/dev/null 2>&1; then D=docker; else D=''sudo docker''; fi',
    # Docker's progress goes to a file, shown only when something fails.
    $(if ($binary) { 'echo Rebuilding the image; $D compose build -q forte >compose.log 2>&1 || { cat compose.log; exit 4; }' }),
    'echo Stopping FORTE',
    '$D compose stop forte >compose.log 2>&1 || { cat compose.log; exit 4; }',
    # A connection FORTE had open (the IDE's) holds its port for up to a minute after it stops, and
    # FORTE does not take a port that is held: it would run without its management port.
    'if command -v ss >/dev/null; then for i in $(seq 1 90); do ss -Htan ''( sport = :61499 )'' | grep -q . || break; [ $i = 1 ] && echo Waiting until port 61499 is free; sleep 1; done; fi',
    'echo Starting FORTE',
    '$D compose up -d --force-recreate forte >compose.log 2>&1 || { cat compose.log; exit 4; }',
    "for i in `$(seq 1 30); do `$D compose logs forte 2>&1 | grep -q '$ready' && break; sleep 1; done",
    # The boot file is read after that line, block by block.
    "for i in `$(seq 1 30); do `$D compose logs forte 2>&1 | grep -q -E 'Bootfile correctly loaded|Boot file error|could not be opened' && break; sleep 1; done",
    '$D compose logs --tail 15 forte',
    "`$D compose logs forte 2>&1 | grep -q '$ready' || exit 5",
    # FORTE runs, but the program asks for a block type this build lacks.
    "`$D compose logs forte 2>&1 | grep -q 'Boot file error' && exit 6; true"
)
& ssh -t $Pi (($remote | Where-Object { $_ }) -join '; ')
$code = $LASTEXITCODE
$ErrorActionPreference = 'Stop'
$address = $Pi.Split('@')[-1]
$answers = {
    $client = New-Object Net.Sockets.TcpClient
    try { $client.ConnectAsync($address, 61499).Wait(5000) -and $client.Connected } catch { $false } finally { $client.Dispose() }
}
switch ($code) {
    0 {
        if (!(& $answers)) { throw "FORTE runs on $Pi but does not answer on ${address}:61499 from this PC. 'bind() failed' in the log above: its port was held, run again. Otherwise: a firewall, or another address?" }
        $what = @($(if ($binary) { 'the new build' }), $(if ($Program) { 'the program from ' + (Split-Path -Leaf $Program) })) | Where-Object { $_ }
        if (!$what) { $what = @('its program') }
        "FORTE runs $($what -join ' with ') on $Pi and answers on ${address}:61499."
        if ($binary) { "  The old binary is ~/$Folder/forte.old." }
        if ($Program) { '  Change the program by running this again with a new boot file, not by Deploy in the IDE.' }
    }
    2 { throw "No folder ~/$Folder on the Pi: install FORTE there first (install-pi.ps1)" }
    3 { throw 'A file on the Pi does not match its checksum; nothing was replaced. Run again.' }
    4 { throw "docker compose failed on the Pi; see: ssh $Pi `"cd $Folder && docker compose logs forte`"" }
    5 { throw "FORTE did not report '$ready' within 30 s; its log is above. Back to the old one: ssh $Pi `"cd $Folder && mv forte.old forte && docker compose up -d --build --force-recreate forte`"" }
    6 {
        if ($Program) { throw "FORTE runs on $Pi, but the program in $(Split-Path -Leaf $Program) uses a block type FORTE lacks, or one changed since FORTE was built; see the boot file error above; nothing of it runs. Build FORTE with the project's types: run again with -Project as well. The program before is ~/$Folder/boot/forte.fboot.old." }
        throw "FORTE runs the new build on $Pi, but the program it has (boot/forte.fboot, from an earlier modsync push, not from -Project) uses a block type this build lacks; see the boot file error above. Its first blocks are created, the rest is not. Give it the project's program (-Program <boot file>), or start without it (-NoProgram)."
    }
    default { throw "ssh to $Pi failed (exit $code)" }
}
