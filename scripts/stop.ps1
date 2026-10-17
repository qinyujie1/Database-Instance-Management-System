$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pidPath = Join-Path $projectRoot '.runtime\processes.json'
if (!(Test-Path -LiteralPath $pidPath)) { Write-Host 'No services recorded.'; exit }
$entries = Get-Content -LiteralPath $pidPath -Raw | ConvertFrom-Json
foreach ($entry in $entries) {
    $process = Get-Process -Id $entry.id -ErrorAction SilentlyContinue
    if ($process -and $process.StartTime.ToUniversalTime().ToString('o') -eq $entry.started) {
        Stop-Process -Id $entry.id
        Write-Host "Stopped $($entry.name)"
    }
}
