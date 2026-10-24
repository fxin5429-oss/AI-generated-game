# 一键启动 Dawn Leap (Windows)
# 优先挑一个已经能 import pygame 的 Python 直接跑; 都没有才去装.
$ErrorActionPreference = "Continue"
Set-Location -Path $PSScriptRoot

# ---------- 候选解释器: 靠前的优先 ----------
$candidates = @()
$venvPy = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (Test-Path $venvPy) { $candidates += @{ exe = $venvPy; pre = @() } }
$candidates += @{ exe = "py";       pre = @("-3") }
$candidates += @{ exe = "python3";  pre = @() }
$candidates += @{ exe = "python";   pre = @() }
$candidates += @{ exe = "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe"; pre = @() }
$candidates += @{ exe = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"; pre = @() }
$candidates += @{ exe = "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe"; pre = @() }
$candidates += @{ exe = "C:\Program Files (x86)\Microsoft Visual Studio\Shared\Python39_64\python.exe"; pre = @() }
# 兜底: DSH 自带的 Python 运行时 (如果存在且装了 pygame)
$candidates += @{ exe = "$env:USERPROFILE\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"; pre = @() }

function Get-PyVersion($exe, $pre) {
    if (-not (Get-Command $exe -ErrorAction SilentlyContinue) -and -not (Test-Path $exe)) { return 0 }
    try {
        $out = & $exe @pre -c "import sys; print(sys.version_info[0]*100+sys.version_info[1])" 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $out) { return 0 }
        return [int]$out
    } catch { return 0 }
}

function Test-HasPygame($exe, $pre) {
    try {
        & $exe @pre -c "import pygame" 2>$null
        if ($LASTEXITCODE -eq 0) { return $true }
        return $false
    } catch {
        return $false
    }
}

Write-Host "==> searching for Python ..." -ForegroundColor Cyan
$python = $null
$pre = @()
$runnable = @()      # 能跑但缺 pygame
foreach ($c in $candidates) {
    $v = Get-PyVersion $c.exe $c.pre
    if ($v -lt 309) { continue }
    if (Test-HasPygame $c.exe $c.pre) {
        Write-Host "    [OK] Python $v with pygame: $($c.exe) $($c.pre -join ' ')" -ForegroundColor Green
        $python = $c.exe
        $pre = $c.pre
        break
    }
    $runnable += $c
    Write-Host "    Python $v found but no pygame: $($c.exe) $($c.pre -join ' ')" -ForegroundColor DarkGray
}

# ---------- 没有现成的, 就装 ----------
if (-not $python) {
    if ($runnable.Count -eq 0) {
        Write-Host ""
        Write-Host "No usable Python 3.9+ found." -ForegroundColor Red
        Write-Host "Install Python first: https://www.python.org/downloads/"
        Write-Host "Remember to check [x] Add python.exe to PATH"
        Write-Host ""
        Read-Host "Press Enter to exit"
        exit 1
    }
    $target = $runnable[0]
    Write-Host ""
    Write-Host "==> pygame is missing, installing (one time, ~11 MB) ..." -ForegroundColor Yellow
    & $target.exe @($target.pre) -m pip install --user --disable-pip-version-check pygame
    if (-not (Test-HasPygame $target.exe $target.pre)) {
        Write-Host ""
        Write-Host "pygame install failed." -ForegroundColor Red
        Write-Host "Run this manually, then start play.bat again:" -ForegroundColor Yellow
        Write-Host ("    " + $target.exe + " " + ($target.pre -join " ") + " -m pip install pygame")
        Write-Host ""
        Read-Host "Press Enter to exit"
        exit 1
    }
    $python = $target.exe; $pre = $target.pre
}

# ---------- 启动 ----------
Write-Host ""
Write-Host "==> starting Dawn Leap ... (close the game window to quit)" -ForegroundColor Green
Write-Host ""
& $python @pre main.py
$code = $LASTEXITCODE

if ($code -ne 0) {
    Write-Host ""
    Write-Host "Game exited with error code $code" -ForegroundColor Red
    Write-Host "Send me the error above and I will fix it." -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
} else {
    Write-Host "Game closed." -ForegroundColor DarkGray
}
