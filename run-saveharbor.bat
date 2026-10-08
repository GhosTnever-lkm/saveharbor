@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% equ 0 (
  py -3 -m saveharbor
) else (
  python -m saveharbor
)
if errorlevel 1 pause
