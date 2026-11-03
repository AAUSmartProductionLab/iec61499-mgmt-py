param(
    # The 4diac project folder (with its <Project>.sys).
    [Parameter(Mandatory)] [string]$Project,
    # The device whose program is made (e.g. FORTE_PI); default: the device whose MGR_ID is -Address.
    [string]$Device,
    # The Pi's address, to find the device by its MGR_ID (192.168.0.42 or 192.168.0.42:61499).
    [string]$Address,
    # Where the boot file goes; default: .cache/<Project>-<Device>.fboot next to this script.
    [string]$Out
)
# A device's program from a 4diac project, as a FORTE boot file: what the IDE deploys to it, so FORTE
# starts with it (update-pi.ps1 -Program) and nothing has to be deployed or deleted while it runs.
# Per resource of the device: the resource, the blocks mapped to it with their parameters, the
# connections between them, then the resource is started. Untyped subapplications become name
# prefixes (Filling.Dispensing.Execute.Home) and connections through their pins are joined, as the
# IDE does; iec61499_mgmt/sysfile.py does the same in Python.
$ErrorActionPreference = 'Stop'
$dir = (Resolve-Path -LiteralPath $Project).Path
$name = Split-Path -Leaf $dir
$sysPath = Join-Path $dir "$name.sys"
if (!(Test-Path -LiteralPath $sysPath)) { throw "$dir has no $name.sys: is it a 4diac project folder?" }
$system = New-Object Xml.XmlDocument
$system.Load($sysPath)
$root = $system.DocumentElement
$unquote = { param($value) "$value".Trim().Trim('"') }

# --- the device -------------------------------------------------------------------------------
$devices = @($root.SelectNodes('Device'))
$managers = $devices | ForEach-Object {
    $id = $_.SelectSingleNode("Parameter[@Name='MGR_ID']")
    '{0} ({1})' -f $_.GetAttribute('Name'), $(if ($id) { & $unquote $id.GetAttribute('Value') } else { 'no MGR_ID' })
}
if ($Device) {
    $dev = $devices | Where-Object { $_.GetAttribute('Name') -eq $Device } | Select-Object -First 1
    if (!$dev) { throw "No device $Device in $name.sys; it has: $($managers -join ', ')" }
} elseif ($Address) {
    $wanted = if ($Address -match ':\d+$') { $Address } else { "${Address}:61499" }
    $dev = @($devices | Where-Object {
        $id = $_.SelectSingleNode("Parameter[@Name='MGR_ID']")
        $id -and (& $unquote $id.GetAttribute('Value')) -eq $wanted
    })
    if ($dev.Count -ne 1) {
        $found = if ($dev.Count) { 'more than one device has' } else { 'no device has' }
        throw "In $name.sys $found MGR_ID $wanted (its devices: $($managers -join ', ')): set the device's MGR_ID in the IDE, or give -Device"
    }
    $dev = $dev[0]
} else { throw 'Give -Device <name> or -Address <the Pi''s address>' }

# --- what is mapped to its resources ----------------------------------------------------------
$mapped = @{}   # application path (App.Block) -> resource
foreach ($m in $root.SelectNodes('Mapping')) {
    $to = $m.GetAttribute('To')
    $dot = $to.IndexOf('.')
    if ($dot -gt 0 -and $to.Substring(0, $dot) -eq $dev.GetAttribute('Name')) { $mapped[$m.GetAttribute('From')] = $to.Substring($dot + 1) }
}
# Its resource: the nearest mapping of the block or of a subapplication around it.
$resourceOf = {
    param($path)
    $parts = $path.Split('.')
    for ($n = $parts.Count; $n -ge 2; $n--) {
        $prefix = $parts[0..($n - 1)] -join '.'
        if ($mapped.ContainsKey($prefix)) { return $mapped[$prefix] }
    }
    $null
}

# Every block of every application (path -> type, parameters), the subapplications' pins, and
# the connections by kind, named by path; in the order the IDE (and sysfile.py) writes them.
$fbs = [ordered]@{}
$parameters = [ordered]@{}
$pins = @{}
$edges = @{ EventConnections = New-Object Collections.ArrayList; DataConnections = New-Object Collections.ArrayList; AdapterConnections = New-Object Collections.ArrayList }
function Walk($network, [string]$prefix) {
    foreach ($fb in $network.SelectNodes('FB')) {
        $path = $prefix + $fb.GetAttribute('Name')
        $fbs[$path] = $fb.GetAttribute('Type')
        foreach ($p in $fb.SelectNodes('Parameter')) { $parameters["$path.$($p.GetAttribute('Name'))"] = $p.GetAttribute('Value') }
    }
    foreach ($sub in $network.SelectNodes('SubApp')) {
        $path = $prefix + $sub.GetAttribute('Name')
        if ($sub.GetAttribute('Type') -and $null -ne (& $resourceOf $path)) { throw "$path is a typed subapplication ($($sub.GetAttribute('Type'))): make the boot file in the IDE instead (right-click the device, Create FORTE Boot-Files)" }
        $iface = $sub.SelectSingleNode('SubAppInterfaceList')
        if (!$iface) { $iface = $sub.SelectSingleNode('InterfaceList') }
        if ($iface) { foreach ($pin in $iface.SelectNodes('*/*')) { $pins["$path.$($pin.GetAttribute('Name'))"] = $true } }
        $inner = $sub.SelectSingleNode('SubAppNetwork')
        if ($inner) { Walk $inner "$path." }
    }
    foreach ($kind in @($edges.Keys)) {
        foreach ($c in $network.SelectNodes("$kind/Connection")) {
            # Bare names inside a subapplication's network are its own pins.
            [void]$edges[$kind].Add(@(($prefix + $c.GetAttribute('Source')), ($prefix + $c.GetAttribute('Destination'))))
        }
    }
}
foreach ($app in $root.SelectNodes('Application')) {
    $network = $app.SelectSingleNode('SubAppNetwork')
    if ($network) { Walk $network "$($app.GetAttribute('Name'))." }
}

# --- the boot file ----------------------------------------------------------------------------
$escape = { param($text) [Security.SecurityElement]::Escape("$text").Replace('&apos;', "'") }
$lines = New-Object Collections.ArrayList
$add = { param($resource, $body) [void]$lines.Add(('{0};<Request ID="{1}" {2}</Request>' -f $resource, ($lines.Count + 1), $body)) }
$resources = @($dev.SelectNodes('Resource'))
foreach ($res in $resources) {
    $resName = $res.GetAttribute('Name')
    $resType = $res.GetAttribute('Type')
    & $add '' ('Action="CREATE"><FB Name="{0}" Type="{1}" />' -f (& $escape $resName), (& $escape $resType))
    # The resource's own blocks, without those of its type (EMB_RES has START).
    $typeName = $resType.Split(':')[-1]
    $typeFile = Get-ChildItem -LiteralPath $dir -Recurse -File -Filter "$typeName.res" | Select-Object -First 1
    $builtIn = @{}
    if ($typeFile) {
        $type = New-Object Xml.XmlDocument
        $type.Load($typeFile.FullName)
        foreach ($fb in $type.SelectNodes('//FBNetwork/FB')) { $builtIn[$fb.GetAttribute('Name')] = $true }
    } elseif ($typeName -eq 'EMB_RES') { $builtIn['START'] = $true }
    $own = [ordered]@{}
    $ownParameters = [ordered]@{}
    $network = $res.SelectSingleNode('FBNetwork')
    if ($network) {
        foreach ($fb in $network.SelectNodes('FB')) {
            if ($builtIn[$fb.GetAttribute('Name')] -or $fb.GetAttribute('Name').Contains('.')) { continue }
            $own[$fb.GetAttribute('Name')] = $fb.GetAttribute('Type')
            foreach ($p in $fb.SelectNodes('Parameter')) { $ownParameters["$($fb.GetAttribute('Name')).$($p.GetAttribute('Name'))"] = $p.GetAttribute('Value') }
        }
    }
    $here = @{}
    foreach ($path in $fbs.Keys) { if ((& $resourceOf $path) -eq $resName) { $here[$path] = $true } }
    foreach ($block in @($own.Keys) + @($builtIn.Keys)) { $here[$block] = $true }
    if ($here.Count -eq $builtIn.Count) { Write-Warning "Nothing is mapped to $($dev.GetAttribute('Name')).$resName" }
    foreach ($path in $own.Keys) { & $add $resName ('Action="CREATE"><FB Name="{0}" Type="{1}" />' -f (& $escape $path), (& $escape $own[$path])) }
    foreach ($path in $fbs.Keys) {
        if ($here[$path]) { & $add $resName ('Action="CREATE"><FB Name="{0}" Type="{1}" />' -f (& $escape $path), (& $escape $fbs[$path])) }
    }
    foreach ($values in $ownParameters, $parameters) {
        foreach ($port in $values.Keys) {
            if (!$here[$port.Substring(0, $port.LastIndexOf('.'))]) { continue }
            & $add $resName ('Action="WRITE"><Connection Source="{0}" Destination="{1}" />' -f (& $escape $values[$port]), (& $escape $port))
        }
    }
    # The connections drawn in the resource (START.COLD to an application's block) belong to it.
    $local = @{ EventConnections = @(); DataConnections = @(); AdapterConnections = @() }
    if ($network) {
        foreach ($kind in @($local.Keys)) { $local[$kind] = @($network.SelectNodes("$kind/Connection") | ForEach-Object { , @($_.GetAttribute('Source'), $_.GetAttribute('Destination')) }) }
    }
    foreach ($kind in 'EventConnections', 'DataConnections', 'AdapterConnections') {
        $all = @($edges[$kind]) + $local[$kind]
        $outgoing = @{}
        foreach ($e in $all) { if (!$outgoing[$e[0]]) { $outgoing[$e[0]] = New-Object Collections.ArrayList }; [void]$outgoing[$e[0]].Add($e[1]) }
        # A pin leads on to the ports it is connected to, through any number of subapplications.
        $ends = {
            param($port, $seen)
            if (!$pins[$port]) { return $port }
            if ($seen -contains $port) { throw "Connection cycle through subapplication pin $port" }
            foreach ($next in @($outgoing[$port])) { if ($next) { & $ends $next (@($seen) + $port) } }
        }
        foreach ($e in $all) {
            if ($pins[$e[0]]) { continue }
            foreach ($to in @(& $ends $e[1] @())) {
                $from = [string]$e[0]
                $fromBlock = $from -replace '\.[^.]*$', ''
                $toBlock = $to -replace '\.[^.]*$', ''
                $ours = $here[$fromBlock], $here[$toBlock]
                if ($ours[0] -and $ours[1]) {
                    & $add $resName ('Action="CREATE"><Connection Source="{0}" Destination="{1}" />' -f (& $escape $from), (& $escape $to))
                } elseif ($ours[0] -or $ours[1]) {
                    Write-Warning "$from -> $to joins $($dev.GetAttribute('Name')).$resName to a block elsewhere: not in this program"
                }
            }
        }
    }
}
foreach ($res in $resources) { & $add '' ('Action="START"><FB Name="{0}" Type="" />' -f (& $escape $res.GetAttribute('Name'))) }

if (!$Out) {
    $cache = Join-Path $PSScriptRoot '.cache'
    New-Item -ItemType Directory -Force -Path $cache | Out-Null
    $Out = Join-Path $cache "$name-$($dev.GetAttribute('Name')).fboot"
}
[IO.File]::WriteAllText($Out, (($lines -join "`n") + "`n"))
$blocks = @($lines | Where-Object { $_ -match 'Action="CREATE"><FB ' }).Count - $resources.Count
"Program of $($dev.GetAttribute('Name')) ($($resources.Count) resource(s), $blocks blocks, $($lines.Count) requests): $Out"
