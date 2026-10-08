param(
    # The FORTE built for the Raspberry Pi (build-modules.ps1 -Config pi/modules-pi).
    [string]$Forte = (Join-Path $PSScriptRoot 'fbe\build\modules-pi\output\bin\forte'),
    # 4diac FORTE Build Environment: its cross toolchain strips the binary.
    [string]$Fbe = 'C:\4diac-fbe'
)
# Put the Pi's FORTE into the repository: runtime/bin/forte-aarch64 (stripped of its debug
# information, 14 MB instead of 73) and its checksum. runtime/install.sh takes it from there, on a
# Pi from a checkout or by download. Run this after a build whose block types changed, and commit
# the two files: a Pi can only run a program whose types its FORTE was built with.
$ErrorActionPreference = 'Stop'
if (!(Test-Path -LiteralPath $Forte)) { throw "$Forte not found; build it with build-modules.ps1 -Config pi/modules-pi -SkipValidate" }
$strip = Join-Path $Fbe 'toolchains\aarch64-linux-musl\bin\aarch64-linux-musl-strip.exe'
if (!(Test-Path -LiteralPath $strip)) { throw "$strip not found (the FBE installs the cross compiler with the first Pi build)" }
$out = Join-Path $PSScriptRoot 'bin'
New-Item -ItemType Directory -Force -Path $out | Out-Null
$binary = Join-Path $out 'forte-aarch64'
Copy-Item -LiteralPath $Forte -Destination $binary -Force
& $strip $binary
if ($LASTEXITCODE -ne 0) { throw 'strip failed' }
$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $binary).Hash.ToLower()
# As sha256sum writes it, with a Unix line end.
[IO.File]::WriteAllText("$binary.sha256", "$hash  forte-aarch64`n")
Get-ChildItem $out | ForEach-Object { Write-Host ("  {0}  {1:N0} bytes" -f $_.Name, $_.Length) }
Write-Host 'Commit runtime/bin/forte-aarch64 and runtime/bin/forte-aarch64.sha256.'
