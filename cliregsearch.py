<# 
.SYNOPSIS
  Search the local Windows Registry for a string.

.EXAMPLE
  .\cliregsearch.ps1 "contoso"

.EXAMPLE
  .\cliregsearch.ps1 "C:\\Program Files" -Hives HKLM,HKCU -View Registry64

.EXAMPLE
  .\cliregsearch.ps1 "Regex\d+" -Regex -MatchCase

.PARAMETER Pattern
  The string or regex to search for.

.PARAMETER Regex
  Treat Pattern as a .NET regular expression (default: plain substring).

.PARAMETER MatchCase
  Case-sensitive match (default: case-insensitive).

.PARAMETER Hives
  One or more of: All, HKLM, HKCU, HKCR, HKU, HKCC (default: All).

.PARAMETER View
  Registry view: Both, Registry64, or Registry32 (default: Both).

.PARAMETER MaxDepth
  Limit recursion depth (0 = unlimited).
#>

[CmdletBinding()]
param(
  [Parameter(Mandatory, Position=0)]
  [string]$Pattern,

  [switch]$Regex,
  [switch]$MatchCase,

  [ValidateSet("All","HKLM","HKCU","HKCR","HKU","HKCC")]
  [string[]]$Hives = @("All"),

  [ValidateSet("Both","Registry64","Registry32")]
  [string]$View = "Both",

  [int]$MaxDepth = 0
)

# --- Helpers ---
function New-Matcher {
  param([string]$Pattern,[switch]$Regex,[switch]$MatchCase)
  if ($Regex) {
    $opts = [System.Text.RegularExpressions.RegexOptions]::None
    if (-not $MatchCase) { $opts = $opts -bor [System.Text.RegularExpressions.RegexOptions]::IgnoreCase }
    $rx = [regex]::new($Pattern, $opts)
    return { param($s) if ($null -ne $s) { $rx.IsMatch([string]$s) } else { $false } }
  } else {
    # plain substring
    $cmp = if ($MatchCase) { 'Ordinal' } else { 'OrdinalIgnoreCase' }
    return { param($s) if ($null -ne $s) { ([string]$s).IndexOf($Pattern, $cmp) -ge 0 } else { $false } }
  }
}

$match = New-Matcher -Pattern $Pattern -Regex:$Regex -MatchCase:$MatchCase

# map hive names to RegistryHive enum
$HiveMap = @{
  HKLM = [Microsoft.Win32.RegistryHive]::LocalMachine
  HKCU = [Microsoft.Win32.RegistryHive]::CurrentUser
  HKCR = [Microsoft.Win32.RegistryHive]::ClassesRoot
  HKU  = [Microsoft.Win32.RegistryHive]::Users
  HKCC = [Microsoft.Win32.RegistryHive]::CurrentConfig
}
if ($Hives -contains 'All') { $Hives = @('HKLM','HKCU','HKCR','HKU','HKCC') }

# which views
$Views = switch ($View) {
  'Registry64' { @([Microsoft.Win32.RegistryView]::Registry64) }
  'Registry32' { @([Microsoft.Win32.RegistryView]::Registry32) }
  default      { @([Microsoft.Win32.RegistryView]::Registry64, [Microsoft.Win32.RegistryView]::Registry32) }
}

# emit a standardized result object
function Write-Hit {
  param(
    [string]$Hive, [string]$View, [string]$Path,
    [string]$Kind, # KeyName | ValueName | ValueData
    [string]$ValueName, [string]$ValueType, [string]$Data
  )
  [pscustomobject]@{
    Hive      = $Hive
    View      = $View
    Path      = $Path
    Kind      = $Kind
    ValueName = if ($ValueName) { $ValueName } else { '(Default)' }
    ValueType = $ValueType
    Data      = $Data
  }
}

# safely enumerate subkeys/values even with access issues
function Get-SubKeyNamesSafe($rk) {
  try { $rk.GetSubKeyNames() } catch { @() }
}
function Get-ValueNamesSafe($rk) {
  try { $rk.GetValueNames() } catch { @() }
}
function Get-ValueSafe($rk,$name,[ref]$kind) {
  try { 
    $k = [Microsoft.Win32.RegistryValueKind]::Unknown
    $val = $rk.GetValue($name, $null, [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
    $k = $rk.GetValueKind($name)
    $kind.Value = $k
    return $val
  } catch { 
    $kind.Value = $null
    return $null
  }
}

# format value data to a short printable snippet
function Format-Data([object]$data, [Microsoft.Win32.RegistryValueKind]$k) {
  switch ($k) {
    'MultiString' { ($data -join '; ') }
    'Binary'      { if ($null -eq $data) { '' } else { ('{0} bytes: ' -f $data.Length) + ($data[0..([math]::Min($data.Length-1,15))] | ForEach-Object { $_.ToString('X2') } -join ' ') + ' ...' } }
    default       { [string]$data }
  }
}

$global:__keyCount = 0
$global:__hitCount = 0
$start = Get-Date

function Search-Key {
  param(
    [Microsoft.Win32.RegistryKey]$Key,
    [string]$HiveLabel,
    [string]$ViewLabel,
    [int]$Depth = 0
  )

  $global:__keyCount++

  $path = $Key.Name
  $leaf = $path -replace '^HKEY_[^\\]+\\',''

  # Progress
  if ($global:__keyCount % 200 -eq 0) {
    $elapsed = (Get-Date) - $start
    Write-Progress -Activity "Searching Registry ($HiveLabel $ViewLabel)" -Status "$global:__keyCount keys scanned, $global:__hitCount hits, elapsed $([int]$elapsed.TotalSeconds)s" -CurrentOperation $leaf -PercentComplete 0
  }

  # 1) match key name
  if ($match.Invoke($leaf)) {
    Write-Hit -Hive $HiveLabel -View $ViewLabel -Path $path -Kind 'KeyName' -ValueName '' -ValueType '' -Data ''
    $global:__hitCount++
  }

  # 2) values: names + data
  $valueNames = Get-ValueNamesSafe $Key
  foreach ($vn in $valueNames) {
    if ($match.Invoke($vn)) {
      $kindTmp = $null
      $val = Get-ValueSafe $Key $vn ([ref]$kindTmp)
      Write-Hit -Hive $HiveLabel -View $ViewLabel -Path $path -Kind 'ValueName' -ValueName $vn -ValueType "$kindTmp" -Data (Format-Data $val $kindTmp)
      $global:__hitCount++
    } else {
      $kindTmp = $null
      $val = Get-ValueSafe $Key $vn ([ref]$kindTmp)
      # Convert common types to string for matching
      $toCheck = switch ($kindTmp) {
        'MultiString' { ($val -join "`n") }
        'Binary'      {  # cheap: hex string for quick substring; skip if Regex to avoid catastrophic backtracking on huge data
                         if ($Regex) { $null } else { if ($val) { ($val | ForEach-Object { $_.ToString('X2') }) -join '' } }
                       }
        default       { [string]$val }
      }
      if ($null -ne $toCheck -and $match.Invoke($toCheck)) {
        Write-Hit -Hive $HiveLabel -View $ViewLabel -Path $path -Kind 'ValueData' -ValueName $vn -ValueType "$kindTmp" -Data (Format-Data $val $kindTmp)
        $global:__hitCount++
      }
    }
  }

  # 3) recurse into subkeys
  if ($MaxDepth -eq 0 -or $Depth -lt $MaxDepth) {
    foreach ($sub in Get-SubKeyNamesSafe $Key) {
      $child = $null
      try { $child = $Key.OpenSubKey($sub, $false) } catch { $child = $null }
      if ($child) {
        try {
          Search-Key -Key $child -HiveLabel $HiveLabel -ViewLabel $ViewLabel -Depth ($Depth + 1)
        } finally {
          $child.Close()
        }
      }
    }
  }
}

$results = New-Object System.Collections.Generic.List[object]

# capture output from Write-Hit
$PSDefaultParameterValues['Write-Hit:OutVariable'] = 'tmpHit'

foreach ($h in $Hives) {
  foreach ($v in $Views) {
    $base = $null
    try {
      $base = [Microsoft.Win32.RegistryKey]::OpenBaseKey($HiveMap[$h], $v)
    } catch {
		Write-Verbose ("Cannot open {0} in {1}: {2}" -f $h, $v, $_.Exception.Message)

		continue
    }
    if (-not $base) { continue }
    try {
      Search-Key -Key $base -HiveLabel $h -ViewLabel $v.ToString()
    } finally {
      $base.Close()
    }
  }
}

# Emit results neatly
$results = $ExecutionContext.SessionState.PSVariable.Get('tmpHit').Value
$results | Sort-Object Hive, View, Path, Kind, ValueName | Format-Table -AutoSize

Write-Host "`nScanned $global:__keyCount keys. Found $global:__hitCount hits."
