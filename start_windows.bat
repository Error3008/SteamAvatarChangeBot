@echo off
chcp 65001 >nul
title Steam Avatar Manager
cd /d "%~dp0"

set "RECOMMENDED_VERSION=3.12"

set "PYTHON_CMD="
where py >nul 2>nul
if %ERRORLEVEL% equ 0 (
    py -3.12 -V >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        set "PYTHON_CMD=py -3.12"
    ) else (
        set "PYTHON_CMD=py"
    )
) else (
    where python >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        set "PYTHON_CMD=python"
    )
)

if "%PYTHON_CMD%"=="" (
    echo ============================================================
    echo  [ERROR] Python is not installed or not added to PATH.
    echo.
    echo  Please download and install Python %RECOMMENDED_VERSION%:
    echo  https://www.python.org/downloads/
    echo.
    echo  IMPORTANT: During installation, be sure to check the box:
    echo  "Add python.exe to PATH"
    echo ============================================================
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('%PYTHON_CMD% -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2^>nul') do set "PY_VER=%%v"

if "%PY_VER%"=="" (
    echo [WARNING] Could not determine Python version.
) else (
    echo [INFO] Detected Python %PY_VER%.
)

if not exist "venv\Scripts\python.exe" (
    echo [SETUP] Creating virtual environment ^(venv^)...
    %PYTHON_CMD% -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [SETUP] Installing dependencies from requirements.txt...
    venv\Scripts\python.exe -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies.
        pause
        exit /b 1
    )
) else (
    venv\Scripts\python.exe -c "import customtkinter, pystray, PIL" >nul 2>nul
    if errorlevel 1 (
        echo [SETUP] Installing / updating missing dependencies...
        venv\Scripts\python.exe -m pip install -r requirements.txt
    )
)

echo [START] Launching Steam Avatar Manager...
if "%1"=="--console" goto run_console
if "%1"=="-c" goto run_console
if "%1"=="--debug" goto run_console

if exist "venv\Scripts\pythonw.exe" (
    start "" "venv\Scripts\pythonw.exe" gui.py
    exit /b 0
)

:run_console
venv\Scripts\python.exe gui.py %*
if errorlevel 1 (
    echo.
    echo ============================================================
    echo  [ERROR] Application exited with an error code.
    echo ============================================================
    pause
)
