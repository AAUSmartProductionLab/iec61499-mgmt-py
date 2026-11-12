# The FORTE of the CIRP paper's evaluation (docs/cirp-evaluation.md, Q1): the lab's FORTE for
# Windows with 0008-connection-query-by-part.patch on top, so a program too large for one answer is
# read back part by part, and with longer event lists (configuration eval/modules-win-eval). Built
# beside the lab's, into runtime/fbe/build/modules-win-eval; the FORTE source is left as it was.
# The same for the module's Pi: -Config eval/modules-pi-eval, into runtime/fbe/build/modules-pi-eval.
#
#     powershell -ExecutionPolicy Bypass -File cell/eval/forte/build.ps1
#     powershell -ExecutionPolicy Bypass -File cell/eval/forte/build.ps1 -Config eval/modules-pi-eval
param(
    # 4diac FORTE Build Environment, as for runtime/build-runtime.ps1.
    [string]$Fbe = 'C:\4diac-fbe',
    # The evaluation's configuration: Windows (the PC) or eval/modules-pi-eval (the module's Pi).
    [string]$Config = 'eval/modules-win-eval'
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$forte = Join-Path $repo 'runtime\fbe\4diac-forte'
$build = Join-Path $repo 'runtime\build-runtime.ps1'
$patch = Join-Path $PSScriptRoot '0008-connection-query-by-part.patch'
# The lab's patches first (runtime/forte-patches), then the evaluation's, undone after the build.
& $build -Fbe $Fbe -FetchOnly
$ErrorActionPreference = 'Continue'
& git -C $forte apply $patch
$ErrorActionPreference = 'Stop'
if ($LASTEXITCODE -ne 0) { throw "Could not apply $patch to runtime/fbe/4diac-forte" }
try {
    & $build -Fbe $Fbe -Config $Config
}
finally {
    $ErrorActionPreference = 'Continue'
    & git -C $forte apply --reverse $patch
    if ($LASTEXITCODE -ne 0) { Write-Warning "Could not undo $patch in runtime/fbe/4diac-forte" }
}
