$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $projectRoot

$buildVenv = Join-Path $projectRoot ".build-venv"
$buildPython = Join-Path $buildVenv "Scripts\python.exe"
$distDirectory = Join-Path $projectRoot "dist"
$workDirectory = Join-Path $projectRoot "build"

if (-not (Test-Path -LiteralPath $buildPython)) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 -m venv $buildVenv
    } else {
        & python -m venv $buildVenv
    }
}

& $buildPython -m pip install --upgrade pip
& $buildPython -m pip install --upgrade -r requirements.txt "pyinstaller>=6.14"
& $buildPython -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name "NEU-WakeUP" `
    --hidden-import qrcode.image.pil `
    --hidden-import PIL.ImageTk `
    --distpath $distDirectory `
    --workpath $workDirectory `
    neuwakeup.py

$exePath = Join-Path $distDirectory "NEU-WakeUP.exe"
if (-not (Test-Path -LiteralPath $exePath)) {
    throw "EXE build failed: $exePath was not created"
}

Write-Host "构建完成：$exePath" -ForegroundColor Green
