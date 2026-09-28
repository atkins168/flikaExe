@echo off
Setlocal EnableDelayedExpansion
chcp 65001 >nul
title Flika Nuitka One-click Build (pywebview)
cd /d %~dp0

REM ===================== 1. Config =====================
REM Modify these for your project
set PYTHON_EXE=.\.venv\Scripts\python.exe
set VENV_DIR=.venv
set ENTRY=flikaExe.py
set ICO=icons\icon.ico
set OUT_DIR=distFlika
set EXE_NAME=flikaExe.exe

REM ===================== 2. Clean old files =====================
echo [1/4] Cleaning old build files...
rmdir /s /q %OUT_DIR% >nul 2>nul
rmdir /s /q %ENTRY:.py=%.build >nul 2>nul
rmdir /s /q %ENTRY:.py=%.onefile-build >nul 2>nul

REM ===================== 3. Nuitka build =====================
echo [2/4] Nuitka building (pywebview)...
%PYTHON_EXE% -m nuitka ^
  --onefile ^
  --msvc=latest ^
  --windows-console-mode=disable ^
  --windows-icon-from-ico=%ICO% ^
  --output-dir=%OUT_DIR% ^
  --output-filename=%EXE_NAME% ^
  --remove-output ^
  --python-flag=-O ^
  --lto=yes ^
  %ENTRY%

if %errorlevel% neq 0 (
    echo [ERROR] Nuitka build failed. See log above.
    pause
    exit /b 1
)

REM ===================== 4. UPX compression (optional) =====================
echo [3/4] UPX compression (if available)...
where upx >nul 2>nul && (
    upx --best --lzma %OUT_DIR%\%EXE_NAME%
) || (
    echo [NOTE] UPX not found, skip compression.
)

echo.
echo ======================== BUILD DONE ========================
echo.
echo [OK] Output: %CD%\%OUT_DIR%\%EXE_NAME%
echo.
pause
