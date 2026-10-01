param(
    # The FORTE built for the Raspberry Pi (build-modules.ps1 -Config pi/modules-pi).
    [string]$Forte = (Join-Path $PSScriptRoot 'fbe\build\modules-pi\output\bin\forte'),
    [string]$Out = (Join-Path $PSScriptRoot 'dist')
)
# Prepare the Pi's FORTE for a GitHub release: runtime/install.sh downloads the asset
# "forte-aarch64" of the latest release and checks it against "forte-aarch64.sha256".
$ErrorActionPreference = 'Stop'
if (!(Test-Path -LiteralPath $Forte)) { throw "$Forte not found; build it with build-modules.ps1 -Config pi/modules-pi -SkipValidate" }
New-Item -ItemType Directory -Force -Path $Out | Out-Null
$asset = Join-Path $Out 'forte-aarch64'
Copy-Item -LiteralPath $Forte -Destination $asset -Force
$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $asset).Hash.ToLower()
# As sha256sum writes it, with a Unix line end.
[IO.File]::WriteAllText("$asset.sha256", "$hash  forte-aarch64`n")
Write-Host "Release assets in ${Out}:"
Get-ChildItem $Out | ForEach-Object { Write-Host ("  {0}  {1:N0} bytes" -f $_.Name, $_.Length) }
Write-Host "Upload both to a release of the repository (GitHub > Releases > Draft a new release),"
Write-Host "or: gh release create runtime-<date> `"$asset`" `"$asset.sha256`" --title `"FORTE runtime for Raspberry Pi`""
