# 一键安装依赖并创建虚拟环境（Windows PowerShell）
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

Write-Host "==> 查找 Python ..." -ForegroundColor Cyan
$candidates = @()
$pyLauncher = Get-Command py -ErrorAction SilentlyContinue
if ($pyLauncher) { $candidates += $pyLauncher.Source }
foreach ($cmd in @("python", "python3")) {
    $c = Get-Command $cmd -ErrorAction SilentlyContinue
    if ($c) { $candidates += $c.Source }
}
$candidates += "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe"
$candidates += "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
$candidates += "C:\Program Files (x86)\Microsoft Visual Studio\Shared\Python39_64\python.exe"

$python = $null
foreach ($p in $candidates) {
    if (-not $p) { continue }
    if (-not (Test-Path $p)) { continue }
    try {
        $v = & $p -c "import sys; print(sys.version_info[0], sys.version_info[1])" 2>$null
        if ($LASTEXITCODE -eq 0 -and $v) { $python = $p; break }
    } catch { }
}

if (-not $python) {
    Write-Host "没有找到可用的 Python，请先安装 Python 3.9+ : https://www.python.org/downloads/" -ForegroundColor Red
    exit 1
}
Write-Host "使用 Python: $python" -ForegroundColor Green

if (-not (Test-Path ".venv")) {
    Write-Host "==> 创建虚拟环境 .venv ..." -ForegroundColor Cyan
    & $python -m venv .venv
}
$venvPy = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
Write-Host "==> 安装依赖 (pygame) ..." -ForegroundColor Cyan
& $venvPy -m pip install --upgrade pip
& $venvPy -m pip install -r requirements.txt

Write-Host ""
Write-Host "完成！启动游戏：" -ForegroundColor Green
Write-Host "    .\.venv\Scripts\python.exe main.py" -ForegroundColor Yellow
