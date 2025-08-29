<# 
.SYNOPSIS
  searches the Windows registry for installed program information

.EXAMPLE
	.\cligetinstalledapps.ps1                                    # Basic scan
    .\cligetinstalledapps.ps1 -FilterName 'Microsoft'            # Filter by name"
#>


param(
    [string]$OutputFile = "",
    [switch]$ExportCSV,
    [switch]$ShowUninstallStrings,
    [string]$FilterName = ""
)

# Registry paths where installed programs are stored
$RegistryPaths = @(
    "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*",
    "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*",
    "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*"
)


# Initialize array to store program information
$InstalledPrograms = @()

# Scan each registry path
foreach ($RegistryPath in $RegistryPaths) {
    try {
        # Get all subkeys (program entries)
        $Programs = Get-ItemProperty $RegistryPath -ErrorAction SilentlyContinue
        
        foreach ($Program in $Programs) {
            # Skip entries without display names or system components
            if ($Program.DisplayName -and -not $Program.SystemComponent) {
                
                # Apply name filter if specified
                if ($FilterName -and $Program.DisplayName -notlike "*$FilterName*") {
                    continue
                }
                
                # Create custom object with program information
                $ProgramInfo = [PSCustomObject]@{
                    Name = $Program.DisplayName
                    Version = $Program.DisplayVersion
                    Publisher = $Program.Publisher
                    InstallDate = $Program.InstallDate
                    InstallLocation = $Program.InstallLocation
                    RegistryPath = $Program.PSPath -replace 'Microsoft.PowerShell.Core\\Registry::', ''
                }
                
                $InstalledPrograms += $ProgramInfo
            }
        }
    }
    catch {
        Write-Warning "Could not access registry path: $RegistryPath"
        Write-Warning $_.Exception.Message
    }
}

# Sort programs by name
$InstalledPrograms = $InstalledPrograms | Sort-Object Name

foreach ($Program in $InstalledPrograms) {
    Write-Host "Name:      " -NoNewline -ForegroundColor Cyan
    Write-Host $Program.Name
    
    if ($Program.Version) {
        Write-Host "Version:   " -NoNewline -ForegroundColor Cyan
        Write-Host $Program.Version
    }
    
    if ($Program.Publisher) {
        Write-Host "Publisher: " -NoNewline -ForegroundColor Cyan
        Write-Host $Program.Publisher
    }
    
    if ($Program.InstallDate) {
        try {
            $FormattedDate = [DateTime]::ParseExact($Program.InstallDate, "yyyyMMdd", $null).ToString("yyyy-MM-dd")
            Write-Host "Date:      " -NoNewline -ForegroundColor Cyan
            Write-Host $FormattedDate
        }
        catch {
            Write-Host "Install Date: " -NoNewline -ForegroundColor Cyan
            Write-Host $Program.InstallDate
        }
    }
    
    if ($Program.InstallLocation) {
        Write-Host "Location:  " -NoNewline -ForegroundColor Cyan
        Write-Host $Program.InstallLocation
    }
    
    Write-Host "Reg. Path: " -NoNewline -ForegroundColor Cyan
    Write-Host $Program.RegistryPath -ForegroundColor Gray
    
	Write-Host "  " 
}

    
try {
	$InstalledPrograms | Export-Csv -Path "cligetinstalledapps.csv" -NoTypeInformation -Encoding UTF8
}
catch {
	Write-Error "Failed to export CSV: $($_.Exception.Message)"
}

# Summary
Write-Host ""
Write-Host "Count: $($InstalledPrograms.Count)"


