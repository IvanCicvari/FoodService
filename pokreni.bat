@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Gdje kupiti?

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo Python nije pronaden.
  echo Instaliraj ga s https://www.python.org/downloads/
  echo Pri instalaciji oznaci "Add python.exe to PATH", pa ponovo pokreni ovu datoteku.
  pause
  exit /b 1
)

%PY% -X utf8 app.py %*
if errorlevel 1 pause
