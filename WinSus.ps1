<# 
  List of quick checks of usual suspects on a suspicious Windows machin
  Usage:  .\WinSus.ps1 [/SFC]
    * Run as local admin
    * This is read-only (except for the directory where the report is created).
#>

[CmdletBinding()]
param([switch]$SFC)

$ErrorActionPreference = 'SilentlyContinue'
$counter = 0

# --- Prep output folder & transcript ---
$caseDir = "$env:COMPUTERNAME"
New-Item -ItemType Directory -Path $caseDir | Out-Null
Start-Transcript -Path (Join-Path $caseDir 'transcript.txt') -Force | Out-Null

function Pad-Num {
    param([int]$Number, [int]$Width = 2)
    return $Number.ToString("D$Width")
}

# (1) Pipeline-aware Write-Out
function Write-Out {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory, Position=0)]
        [string]$File,

        [Parameter(ValueFromPipeline=$true)]
        $Data
    )
    begin { $buf = New-Object System.Collections.Generic.List[object] }
    process { $buf.Add($Data) }
    end {
        if ($buf.Count -eq 0) { $buf.Add("<no data>") }
        $p = Join-Path $caseDir $File
        $buf | Out-File -FilePath $p -Width 500 -Encoding UTF8
        Write-Host $File
    }
}

# (2) Fixed suspicious path test (removed comma; corrected admin-share regex)
function Test-SuspiciousPath([string]$p) {
    if ([string]::IsNullOrWhiteSpace($p)) { return $false }
    $p = $p.ToLower()

    $isUserPath   = $p -match '\\users\\'
    $isAppData    = $p -match '\\appdata\\'
    $isProgData   = $p -match '\\programdata\\'
    $isTemp       = $p -match '\\temp\\'
    $isUNC        = $p -match '^\\\\'
    $isAdminShare = $p -match '^\\\\[^\\]+\\[a-z]\$$'  # e.g. \\host\c$

    return ($isUserPath -or $isAppData -or $isProgData -or $isTemp -or $isUNC -or $isAdminShare)
}

# --- 0) System basics ---
$sys = [ordered]@{
  ComputerName = $env:COMPUTERNAME
  UserName     = $env:USERNAME
  Domain       = $env:USERDOMAIN
  OS           = (Get-CimInstance Win32_OperatingSystem).Caption
  OSVersion    = (Get-CimInstance Win32_OperatingSystem).Version
  LastBoot     = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime
  UptimeHours  = [int]((New-TimeSpan -Start (Get-CimInstance Win32_OperatingSystem).LastBootUpTime -End (Get-Date)).TotalHours)
  IsAdmin      = ([bool]([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator))
}
$sys | ConvertTo-Json -Depth 4 | Write-Out "$($(Pad-Num $counter))_system.json"
$counter++

# --- Logged-in users & local accounts ---
$who     = (quser 2>$null) -join "`r`n"
$locUser = Get-LocalUser | Select-Object Name,Enabled,LastLogon
$admins  = (Get-LocalGroupMember -Group 'Administrators' 2>$null) | Select-Object ObjectClass,Name,SID
$locUser | Format-Table | Out-String | Write-Out "$($(Pad-Num $counter))_local_users.txt"
$counter++
$admins  | Format-Table | Out-String | Write-Out "$($(Pad-Num $counter))_local_admins.txt"
$counter++

# --- Startup locations (Run/RunOnce + Startup folders) ---
$runKeys = @(
  'HKLM:\Software\Microsoft\Windows\CurrentVersion\Run',
  'HKLM:\Software\Microsoft\Windows\CurrentVersion\RunOnce',
  'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run',
  'HKCU:\Software\Microsoft\Windows\CurrentVersion\RunOnce'
)
$startup = foreach ($rk in $runKeys) {
  if (Test-Path $rk) {
    Get-ItemProperty $rk | ForEach-Object {
      $_.PSObject.Properties |
        Where-Object { $_.Name -notmatch 'PSPath|PSParentPath|PSChildName|PSDrive|PSProvider' } |
        ForEach-Object {
          [pscustomobject]@{
            Hive       = $rk
            Name       = $_.Name
            Command    = $_.Value
            Suspicious = Test-SuspiciousPath($_.Value)
          }
        }
    }
  }
}
$startup | Sort-Object Suspicious -Descending | Export-Csv (Join-Path $caseDir "$($(Pad-Num $counter))_startup_registry.csv") -NoTypeInformation
# (4) Print filename, don't create a new file
Write-Host "$($(Pad-Num $counter))_startup_registry.csv"
$counter++

$startupDirs = @(
  "$env:ProgramData\Microsoft\Windows\Start Menu\Programs\Startup",
  "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup"
)
$startupFiles = foreach ($d in $startupDirs) {
  if (Test-Path $d) {
    Get-ChildItem -Path $d -File -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
      [pscustomobject]@{ Path=$_.FullName; Size=$_.Length; LastWrite=$_.LastWriteTime }
    }
  }
}
$startupFiles | Export-Csv (Join-Path $caseDir "$($(Pad-Num $counter))_startup_folders.csv") -NoTypeInformation
Write-Host "$($(Pad-Num $counter))_startup_folders.csv"
$counter++

# --- Scheduled tasks (all + suspicious paths) ---
$tasksRaw = schtasks /query /fo CSV /v 2>$null | ConvertFrom-Csv
$tasksRaw | Export-Csv (Join-Path $caseDir "$($(Pad-Num $counter))_schtasks_all.csv") -NoTypeInformation
Write-Host "$($(Pad-Num $counter))_schtasks_all.csv"
$counter++

$tasksSus = $tasksRaw | Where-Object {
  $_.'Task To Run' -and (Test-SuspiciousPath $_.'Task To Run') -or
  ($_.Schedule -match 'ONSTART|ONLOGON')
}
$tasksSus | Export-Csv (Join-Path $caseDir "$($(Pad-Num $counter))_schtasks_suspicious.csv") -NoTypeInformation
Write-Host "$($(Pad-Num $counter))_schtasks_suspicious.csv"
$counter++

# --- Services (auto-start + odd paths + unsigned) ---
$svc = Get-CimInstance Win32_Service | Select-Object Name,DisplayName,State,StartMode,PathName
$svcAuto = $svc | Where-Object StartMode -in 'Auto','Automatic','Auto (Delayed Start)'
$svcAuto | Export-Csv (Join-Path $caseDir "$($(Pad-Num $counter))_services_auto.csv") -NoTypeInformation
Write-Host "$($(Pad-Num $counter))_services_auto.csv"
$counter++

# Signature check for service binaries (unique paths)
$svcPaths = $svcAuto.PathName | ForEach-Object {
  ($_ -replace '"','') -split '\s+' | Select-Object -First 1
} | Where-Object { $_ -and (Test-Path $_) } | Select-Object -Unique

$svcSig = foreach ($p in $svcPaths) {
  $sig = Get-AuthenticodeSignature -FilePath $p
  [pscustomobject]@{
    Path=$p
    IsSigned=($sig.SignerCertificate -ne $null)
    Status=$sig.Status
    Subject=$sig.SignerCertificate.Subject
    NotAfter=$sig.SignerCertificate.NotAfter
    Suspicious=Test-SuspiciousPath($p)
  }
}
$svcSig | Export-Csv (Join-Path $caseDir "$($(Pad-Num $counter))_services_binaries_signing.csv") -NoTypeInformation
Write-Host "$($(Pad-Num $counter))_services_binaries_signing.csv"
$counter++

# --- Processes (owner, cmdline, signature) ---
$procs = Get-CimInstance Win32_Process |
  Select-Object Name,ProcessId,CommandLine,ExecutablePath,CreationDate

# owners
$procOwner = @{}
foreach ($p in $procs) {
  try {
    $o = Invoke-CimMethod -InputObject $p -MethodName GetOwner
    $procOwner[$p.ProcessId] = if ($o.ReturnValue -eq 0) { "$($o.Domain)\$($o.User)" } else { "<unknown>" }
  } catch { $procOwner[$p.ProcessId] = "<error>" }
}

$procList = foreach ($p in $procs) {
  $path = $p.ExecutablePath
  $signed = $null
  $status = $null
  if ($path -and (Test-Path $path)) {
    $s = Get-AuthenticodeSignature -FilePath $path
    $signed = ($s.SignerCertificate -ne $null)
    $status = $s.Status
  }
  [pscustomobject]@{
    Name         = $p.Name
    PID          = $p.ProcessId
    Owner        = $procOwner[$p.ProcessId]
    Path         = $path
    CmdLine      = $p.CommandLine
    Started      = $p.CreationDate
    IsSigned     = $signed
    SigStatus    = $status
    Suspicious   = Test-SuspiciousPath($path) -or ($signed -eq $false)
  }
}

# (3) Sort Suspicious desc, Name asc
$procList |
  Sort-Object -Property @{Expression='Suspicious';Descending=$true},
                         @{Expression='Name';Descending=$false} |
  Export-Csv (Join-Path $caseDir "$($(Pad-Num $counter))_processes.csv") -NoTypeInformation
Write-Host "$($(Pad-Num $counter))_processes.csv"
$counter++

# --- Network (current TCP/UDP + mapping to PID) ---
$tcp = Get-NetTCPConnection -ErrorAction SilentlyContinue | Select-Object State,LocalAddress,LocalPort,RemoteAddress,RemotePort,OwningProcess
$udp = Get-NetUDPEndpoint  -ErrorAction SilentlyContinue | Select-Object LocalAddress,LocalPort,OwningProcess
$tasks = Get-Process | Select-Object Id,Name,Path

$tcpEnriched = foreach ($t in $tcp) {
  $p = $tasks | Where-Object Id -eq $t.OwningProcess
  [pscustomobject]@{
    State         = $t.State
    LAddr         = $t.LocalAddress
    LPort         = $t.LocalPort
    RAddr         = $t.RemoteAddress
    RPort         = $t.RemotePort
    PID           = $t.OwningProcess
    ProcName      = $p.Name
    ProcPath      = $p.Path
  }
}
$udpEnriched = foreach ($u in $udp) {
  $p = $tasks | Where-Object Id -eq $u.OwningProcess
  [pscustomobject]@{
    LAddr    = $u.LocalAddress
    LPort    = $u.LocalPort
    PID      = $u.OwningProcess
    ProcName = $p.Name
    ProcPath = $p.Path
  }
}

$tcpEnriched | Export-Csv (Join-Path $caseDir "$($(Pad-Num $counter))_tcp.csv") -NoTypeInformation
Write-Host "$($(Pad-Num $counter))_tcp.csv"
$counter++
$udpEnriched | Export-Csv (Join-Path $caseDir "$($(Pad-Num $counter))_udp.csv") -NoTypeInformation
Write-Host "$($(Pad-Num $counter))_udp.csv"
$counter++

# Raw netstat (for cross-check)
(netstat -ano 2>$null) | Out-File (Join-Path $caseDir "$($(Pad-Num $counter))_netstat.txt")
Write-Host "$($(Pad-Num $counter))_netstat.txt"
$counter++

# --- Event Logs (last 48 hours) ---
$since = (Get-Date).AddHours(-48)

# Security: 4624 (logons), 1102 (audit cleared)
$ev4624 = Get-WinEvent -FilterHashtable @{LogName='Security'; Id=4624; StartTime=$since} -ErrorAction SilentlyContinue |
  Select-Object TimeCreated, Id, ProviderName, @{n='TargetUser';e={$_.Properties[5].Value}}, @{n='Ip';e={$_.Properties[18].Value}}, Message
$ev1102 = Get-WinEvent -FilterHashtable @{LogName='Security'; Id=1102; StartTime=$since} -ErrorAction SilentlyContinue |
  Select-Object TimeCreated, Id, ProviderName, Message

# System: 7045 (service installed), 6005/6006 (event log start/stop), 7036 (service state change)
$ev7045 = Get-WinEvent -FilterHashtable @{LogName='System'; Id=7045; StartTime=$since} -ErrorAction SilentlyContinue |
  Select-Object TimeCreated, Id, ProviderName, Message
$ev7036 = Get-WinEvent -FilterHashtable @{LogName='System'; Id=7036; StartTime=$since} -ErrorAction SilentlyContinue |
  Select-Object TimeCreated, Id, ProviderName, Message

$ev4624 | Export-Csv (Join-Path $caseDir "$($(Pad-Num $counter))_ev_security_4624.csv") -NoTypeInformation
Write-Host "$($(Pad-Num $counter))_ev_security_4624.csv"
$counter++
$ev1102 | Export-Csv (Join-Path $caseDir "$($(Pad-Num $counter))_ev_security_1102.csv") -NoTypeInformation
Write-Host "$($(Pad-Num $counter))_ev_security_1102.csv"
$counter++
$ev7045 | Export-Csv (Join-Path $caseDir "$($(Pad-Num $counter))_ev_system_7045.csv")  -NoTypeInformation
Write-Host "$($(Pad-Num $counter))_ev_system_7045.csv"
$counter++
$ev7036 | Export-Csv (Join-Path $caseDir "$($(Pad-Num $counter))_ev_system_7036.csv")  -NoTypeInformation
Write-Host "$($(Pad-Num $counter))_ev_system_7036.csv"
$counter++

# --- Firewall & DNS cache (if present) ---
$fwLog = "$env:SystemRoot\System32\LogFiles\Firewall\pfirewall.log"
if (Test-Path $fwLog) {
  Get-Content $fwLog -Tail 5000 | Out-File (Join-Path $caseDir "$($(Pad-Num $counter))_firewall_tail.txt")
}
Write-Host "$($(Pad-Num $counter))_firewall_tail.txt"
$counter++

(ipconfig /displaydns 2>$null) | Out-File (Join-Path $caseDir "$($(Pad-Num $counter))_dns_cache.txt")
Write-Host "$($(Pad-Num $counter))_dns_cache.txt"
$counter++

# --- Integrity (optional fast checks + optional SFC) ---
dism /Online /Cleanup-Image /CheckHealth | Out-File (Join-Path $caseDir "$($(Pad-Num $counter))_dism_checkhealth.txt")
Write-Host "$($(Pad-Num $counter))_dism_checkhealth.txt"
$counter++

if ($SFC) {
  sfc /scannow | Out-File (Join-Path $caseDir "$($(Pad-Num $counter))_sfc_scannow.txt")
  Write-Host "$($(Pad-Num $counter))_sfc_scannow.txt"
  $counter++
}

# --- Environment & artifacts quick sweep ---
$envInfo = Get-ChildItem Env: | Sort-Object Name
$envInfo | Format-Table | Out-String | Write-Out "$($(Pad-Num $counter))_env.txt"
$counter++

# Common LOLBins presence quick list
$lolbins = @(
  "$env:SystemRoot\System32\certutil.exe",
  "$env:SystemRoot\System32\bitsadmin.exe",
  "$env:SystemRoot\System32\mshta.exe",
  "$env:SystemRoot\System32\regsvr32.exe",
  "$env:SystemRoot\System32\rundll32.exe",
  "$env:SystemRoot\System32\wscript.exe",
  "$env:SystemRoot\System32\cscript.exe",
  "$env:SystemRoot\System32\powershell.exe",
  "$env:SystemRoot\System32\curl.exe",
  "$env:SystemRoot\System32\esentutl.exe"
) | ForEach-Object {
  [pscustomobject]@{ Path = $_; Exists = (Test-Path $_) }
}
$lolbins | Export-Csv (Join-Path $caseDir "$($(Pad-Num $counter))_lolbins_present.csv") -NoTypeInformation
Write-Host "$($(Pad-Num $counter))_lolbins_present.csv"

Stop-Transcript | Out-Null
Write-Host "`nResults saved to: $caseDir" -ForegroundColor Green
