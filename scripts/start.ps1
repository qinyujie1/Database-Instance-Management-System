$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
$runtimePath = Join-Path $projectRoot '.runtime'
New-Item -ItemType Directory -Path $runtimePath -Force | Out-Null
$pidPath = Join-Path $runtimePath 'processes.json'
if (Test-Path -LiteralPath $pidPath) {
    $existing = Get-Content -LiteralPath $pidPath -Raw | ConvertFrom-Json
    foreach ($entry in $existing) {
        if (Get-Process -Id $entry.id -ErrorAction SilentlyContinue) { throw 'Existing services detected. Run scripts/stop.ps1 before restarting.' }
    }
}
$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 8010)
try { $listener.Start() } finally { $listener.Stop() }
$services = @(
    @{ name = 'web'; arguments = @('manage.py', 'runserver', '127.0.0.1:8010', '--noreload') },
    @{ name = 'worker'; arguments = @('-m', 'celery', '-A', 'config', 'worker', '--pool=solo', '--concurrency=1', '--loglevel=INFO', '--without-gossip', '--without-mingle') },
    @{ name = 'beat'; arguments = @('-m', 'celery', '-A', 'config', 'beat', '--loglevel=INFO', '--schedule=.runtime/celerybeat-schedule') }
)
$started = @()
foreach ($service in $services) {
    $process = Start-Process -FilePath $pythonPath -ArgumentList $service.arguments -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimePath ($service.name + '.out.log')) -RedirectStandardError (Join-Path $runtimePath ($service.name + '.err.log'))
    $started += @{ name = $service.name; id = $process.Id; started = $process.StartTime.ToUniversalTime().ToString('o') }
    ConvertTo-Json -InputObject @($started) | Set-Content -LiteralPath $pidPath
}
Write-Host 'Started: http://127.0.0.1:8010/ (logs in .runtime/)'
