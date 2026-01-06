@echo off
REM ============================================================================
REM Titan-Quant Server Startup Script (Windows)
REM ============================================================================
REM This script starts the Titan-Quant backend server (Python daemon).
REM The server provides WebSocket communication for the UI client.
REM
REM Usage:
REM   start_server.bat [options]
REM
REM Options:
REM   --host HOST     Server host address (default: 127.0.0.1)
REM   --port PORT     Server port number (default: 8765)
REM   --debug         Enable debug logging
REM   --help          Show this help message
REM ============================================================================

setlocal enabledelayedexpansion

REM Get the script directory (bin/)
set "SCRIPT_DIR=%~dp0"
REM Get the project root directory (parent of bin/)
set "PROJECT_ROOT=%SCRIPT_DIR%.."
cd /d "%PROJECT_ROOT%"

REM Default configuration
set "HOST=127.0.0.1"
set "PORT=8765"
set "DEBUG="
set "VENV_DIR=.venv"

REM Parse command line arguments
:parse_args
if "%~1"=="" goto :check_env
if /i "%~1"=="--host" (
    set "HOST=%~2"
    shift
    shift
    goto :parse_args
)
if /i "%~1"=="--port" (
    set "PORT=%~2"
    shift
    shift
    goto :parse_args
)
if /i "%~1"=="--debug" (
    set "DEBUG=--debug"
    shift
    goto :parse_args
)
if /i "%~1"=="--help" (
    goto :show_help
)
shift
goto :parse_args

:show_help
echo.
echo Titan-Quant Server Startup Script
echo ==================================
echo.
echo Usage: start_server.bat [options]
echo.
echo Options:
echo   --host HOST     Server host address (default: 127.0.0.1)
echo   --port PORT     Server port number (default: 8765)
echo   --debug         Enable debug logging
echo   --help          Show this help message
echo.
echo Examples:
echo   start_server.bat
echo   start_server.bat --port 9000
echo   start_server.bat --host 0.0.0.0 --port 8765 --debug
echo.
exit /b 0

:check_env
echo.
echo ============================================
echo   Titan-Quant Server Startup
echo ============================================
echo.

REM Check if Python is available
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    exit /b 1
)

REM Check Python version
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set "PYTHON_VERSION=%%i"
echo [INFO] Python version: %PYTHON_VERSION%

REM Check if virtual environment exists
if exist "%VENV_DIR%\Scripts\activate.bat" (
    echo [INFO] Activating virtual environment...
    call "%VENV_DIR%\Scripts\activate.bat"
) else (
    echo [WARN] Virtual environment not found at %VENV_DIR%
    echo [INFO] Using system Python installation
)

REM Check if required packages are installed
python -c "import websockets" >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARN] Required packages not installed.
    echo [INFO] Installing dependencies from requirements.txt...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install dependencies.
        exit /b 1
    )
)

REM Create necessary directories
if not exist "logs" mkdir logs
if not exist "database\bars" mkdir database\bars
if not exist "database\ticks" mkdir database\ticks
if not exist "database\cache" mkdir database\cache
if not exist "reports" mkdir reports

REM Set environment variables
set "PYTHONPATH=%PROJECT_ROOT%"
set "TITAN_QUANT_HOST=%HOST%"
set "TITAN_QUANT_PORT=%PORT%"

echo.
echo [INFO] Starting Titan-Quant Server...
echo [INFO] Host: %HOST%
echo [INFO] Port: %PORT%
if defined DEBUG echo [INFO] Debug mode: enabled
echo.
echo Press Ctrl+C to stop the server.
echo ============================================
echo.

REM Start the server
python -m core.server %DEBUG% --host %HOST% --port %PORT%

REM Check exit code
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Server exited with error code: %errorlevel%
    exit /b %errorlevel%
)

echo.
echo [INFO] Server stopped.
exit /b 0
