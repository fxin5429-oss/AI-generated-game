@echo off
rem 双击本文件：把「晨光跳跃」打包成一个单独的 exe
rem 结果在 dist\DawnLeap.exe，可以拷到任何地方双击运行
setlocal
cd /d "%~dp0"

echo ==^> looking for Python ...
set "PY="
py -3 -c "import sys" >nul 2>&1 && set "PY=py -3"
if not defined PY (
  python -c "import sys" >nul 2>&1 && set "PY=python"
)
if not defined PY (
  python3 -c "import sys" >nul 2>&1 && set "PY=python3"
)
if not defined PY (
  echo     No Python found. Install Python 3.9+ first:
  echo     https://www.python.org/downloads/
  echo     Remember to tick [Add python.exe to PATH] while installing.
  pause
  exit /b 1
)
echo     using: %PY%

echo ==^> checking pygame ...
%PY% -c "import pygame" >nul 2>&1
if errorlevel 1 (
  echo     installing pygame ...
  %PY% -m pip install pygame
)

echo ==^> checking PyInstaller ...
%PY% -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
  echo     installing PyInstaller ^(one time, about 10 MB^) ...
  %PY% -m pip install pyinstaller
)

echo ==^> building ... please wait, this takes about half a minute
%PY% -m PyInstaller --noconfirm --onefile --windowed --name DawnLeap main.py
if errorlevel 1 (
  echo.
  echo     Build failed. Scroll up for the error message.
  pause
  exit /b 1
)

echo.
echo Done. Your game is here:  dist\DawnLeap.exe
echo That one file is the whole game - copy it anywhere and double-click it.
echo.
pause
