$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$existing = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($existing) { Write-Output 'Port 8000 already in use. Open http://127.0.0.1:8000'; exit }
New-Item -ItemType Directory -Force .local | Out-Null
$p = Start-Process -FilePath "$PSScriptRoot\.venv\Scripts\python.exe" -ArgumentList '-m uvicorn main:app --host 127.0.0.1 --port 8000' -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput "$PSScriptRoot\.local\server.out.log" -RedirectStandardError "$PSScriptRoot\.local\server.err.log" -PassThru
$p.Id | Set-Content "$PSScriptRoot\.local\server.pid"
Write-Output "Started PID $($p.Id): http://127.0.0.1:8000"
