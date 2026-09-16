# Start WordReel API + Web (Windows PowerShell)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

# API
$apiDir = Join-Path $root "apps\api"
$py = Join-Path $apiDir ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
  Write-Host "Creating API venv..."
  Set-Location $apiDir
  python -m venv .venv
  & $py -m pip install -r requirements.txt -q
}
# Optional ffmpeg for audio clips
$ff = Get-Command ffmpeg -ErrorAction SilentlyContinue
if ($ff) {
  $env:FFMPEG_PATH = $ff.Source
} else {
  $wingetFf = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter ffmpeg.exe -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($wingetFf) { $env:FFMPEG_PATH = $wingetFf.FullName }
}
if ($env:FFMPEG_PATH) { Write-Host "ffmpeg: $env:FFMPEG_PATH" }

Start-Process -FilePath $py -ArgumentList "-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8000" -WorkingDirectory $apiDir -WindowStyle Hidden
Write-Host "API  http://127.0.0.1:8000"

# Web
$webDir = Join-Path $root "apps\web"
if (-not (Test-Path (Join-Path $webDir "node_modules"))) {
  Write-Host "Installing web deps..."
  Set-Location $webDir
  npm install
}
Start-Process -FilePath "node" -ArgumentList "node_modules\vite\bin\vite.js","--host","127.0.0.1","--port","5173" -WorkingDirectory $webDir -WindowStyle Hidden
Write-Host "Web  http://127.0.0.1:5173"
Write-Host "Demo account after register: any email + password >= 6 chars (e.g. demo@leran.local / demo1234)"
