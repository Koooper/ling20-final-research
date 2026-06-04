@echo off
REM ============================================================
REM  Double-click this file to set up the analysis environment.
REM  It installs Python (if needed), builds an isolated
REM  environment, and installs the required packages.
REM  No prior knowledge or admin rights needed.
REM ============================================================
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1" %*
echo.
echo Press any key to close this window.
pause >nul
