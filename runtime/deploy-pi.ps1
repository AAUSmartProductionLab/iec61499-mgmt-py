param(
    # The Pi's login and address, e.g. pi@192.168.0.42. It already runs FORTE in Docker from ~/forte
    # (install-pi.ps1 did that once).
    [Parameter(Mandatory)] [string]$Pi,
    # The 4diac project folder (with its <Project>.sys): its program and its block types go to the Pi.
    [Parameter(Mandatory)] [string]$Project,
    # The project's device for this Pi; default: the device whose MGR_ID is the Pi's address.
    [string]$Device,
    # The 4diac IDE (4diac-idec.exe); default: FORDIAC_IDE.
    [string]$Ide,
    # Send the last build (bin/forte-aarch64) instead of building FORTE again: when no block type
    # changed since.
    [switch]$SkipBuild,
    # FORTE's folder on the Pi, below the login's home.
    [string]$Folder = 'forte',
    # Do not ask before FORTE restarts on the Pi.
    [switch]$Force
)
# A 4diac project onto a Pi, from fresh, in one go:
#   1. make-bootfile.ps1: the program of the project's device for this Pi, from the .sys (the blocks
#      mapped to it, their parameters and connections), as a boot file,
#   2. build-project.ps1: FORTE with the project's block types,
#   3. update-pi.ps1: on the Pi, stop and delete the FORTE container, put the new binary and the
#      program in place, build the image and run a new container, which starts with the program.
# Nothing is deployed from the IDE: a deployment deletes the running program first, and FORTE
# crashes doing so when it has GPIO blocks.
$ErrorActionPreference = 'Stop'
$dir = (Resolve-Path -LiteralPath $Project).Path
$name = Split-Path -Leaf $dir
$cache = Join-Path $PSScriptRoot '.cache'
New-Item -ItemType Directory -Force -Path $cache | Out-Null
$program = Join-Path $cache "$name-program.fboot"
$extract = @{ Project = $dir; Out = $program }
if ($Device) { $extract.Device = $Device } else { $extract.Address = $Pi.Split('@')[-1] }
& (Join-Path $PSScriptRoot 'make-bootfile.ps1') @extract
$blocks = @(Get-Content -LiteralPath $program | Where-Object { $_ -match '^[^;]+;<Request [^>]*Action="CREATE"><FB ' })
if (!$blocks) { throw "Nothing of $name is mapped to that device: map the application to the device's resource in the IDE (Map to ...)" }

$update = @{ Pi = $Pi; Program = $program; Folder = $Folder }
if ($SkipBuild) { $update.SkipBuild = $true } else { $update.Project = $dir }
if ($Ide) { $update.Ide = $Ide }
if ($Force) { $update.Force = $true }
& (Join-Path $PSScriptRoot 'update-pi.ps1') @update
