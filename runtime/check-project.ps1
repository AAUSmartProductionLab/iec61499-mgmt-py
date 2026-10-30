param(
    # A 4diac project folder (its name is also the .sys name), e.g. cell/control/FillingModule.
    [Parameter(Mandatory)] [string]$ProjectDir,
    # The 4diac IDE 3.3; elsewhere set FORDIAC_IDE to its 4diac-idec.exe.
    [string]$Ide = $(if ($env:FORDIAC_IDE) { $env:FORDIAC_IDE } else { 'C:\Users\marti\Downloads\4diac-ide_3.2.1-win32.win32.x86_64\4diac-ide\4diac-idec.exe' })
)
# Import a 4diac project headless and run the IDE's own checks: the type library (every type
# loads and compiles; the IDE treats ST warnings as failures) and the system (connections, and
# blocks that overlap in an application or a resource view). Nothing is exported or built; for
# that, runtime/build-modules.ps1 runs validate.ps1. Resource views always report collisions:
# the IDE draws mapped blocks there at their positions inside their groups.
$ErrorActionPreference = 'Stop'
$projectDir = (Resolve-Path -LiteralPath $ProjectDir).Path
$name = Split-Path -Leaf $projectDir
$cache = Join-Path $PSScriptRoot '.cache'
$workspace = Join-Path $cache ('check-' + [guid]::NewGuid().ToString('N'))
$buildfile = Join-Path $cache 'check-project.xml'
$log = Join-Path $cache "check-$name.log"
New-Item -ItemType Directory -Force -Path $cache | Out-Null
$checks = '<fordiac.checkTypeLibrary projectName="${project.name}" />'
if (Test-Path -LiteralPath (Join-Path $projectDir "$name.sys")) {
    $checks += "`n    " + '<fordiac.checkSystem systemPath="${project.name}/${project.name}.sys" />'
}
@"
<?xml version="1.0" encoding="UTF-8"?>
<project name="check" default="check">
  <target name="check">
    <fordiac.importProject projectPath="`${project.path}" />
    <eclipse.incrementalBuild kind="full" />
    $checks
  </target>
</project>
"@ | Set-Content -Encoding utf8 -LiteralPath $buildfile
$ErrorActionPreference = 'Continue'
& $Ide -nosplash --launcher.suppressErrors -application org.eclipse.ant.core.antRunner -data $workspace `
    -buildfile $buildfile "-Dproject.path=$projectDir" "-Dproject.name=$name" -vmargs -Djava.awt.headless=true *> $log
$result = $LASTEXITCODE
$lines = Get-Content -LiteralPath $log
$types = $lines | Where-Object { $_ -match 'checkTypeLibrary\] (ERROR|WARNING)' } | ForEach-Object { $_ -replace '^.*checkTypeLibrary\] ', '' }
$system = $lines | Where-Object { $_ -match 'checkSystem\]' }
"$name`: IDE exit $result"
"type library: $(@($types).Count) errors and warnings"
$types | Select-Object -First 20
"application collisions: $(@($system | Where-Object { $_ -match 'Collision' -and $_ -notmatch 'between FORTE_' }).Count)"
"resource view collisions: $(@($system | Where-Object { $_ -match 'Collision between FORTE_' }).Count) (expected)"
$system | Where-Object { $_ -notmatch 'Collision between FORTE_' } | Select-Object -First 20
$eclipseLog = Join-Path $workspace '.metadata\.log'
if (Test-Path -LiteralPath $eclipseLog) {
    Select-String -LiteralPath $eclipseLog -Pattern 'Error loading|Could not load|Exception' | Select-Object -First 5
}
"log: $log"
