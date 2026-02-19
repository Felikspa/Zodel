@echo off
setlocal

echo ==============================
echo  ZODEL Deployment Script
echo ==============================
echo.
echo  Please select run mode:
echo.
echo    [1] Docker (recommended for production)
echo    [2] Local  (for development/debugging)
echo.
echo  Enter your choice (1 or 2):
set /p CHOICE=

if "%CHOICE%"=="1" goto DOCKER
if "%CHOICE%"=="2" goto LOCAL

echo Invalid choice. Please enter 1 or 2.
pause
exit /b 1

:DOCKER
echo.
echo ==============================
echo  Running in Docker mode
echo ==============================
echo.

echo [1/3] Checking Docker installation...
docker --version >nul 2>&1
if errorlevel 1 (
  echo Docker command not found. Please install Docker Desktop and try again.
  pause
  exit /b 1
)

echo [2/3] Building and starting containers with docker compose...
docker compose up --build -d
if errorlevel 1 (
  echo docker compose failed, trying docker-compose...
  docker-compose up --build -d
  if errorlevel 1 (
    echo Failed to start. Please make sure docker compose or docker-compose is installed.
    pause
    exit /b 1
  )
)

echo.
echo [3/3] ZODEL should now be running:
echo   API:   http://localhost:8000
echo   WebUI: http://localhost:3000
echo.
echo Use "docker compose logs -f" to see logs, or "docker compose down" to stop services.

pause
goto END

:LOCAL
echo.
echo ==============================
echo  Running in Local mode
echo ==============================
echo.

REM Check if Python is available
echo [1/5] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
  echo Python not found. Please install Python 3.10+ and try again.
  pause
  exit /b 1
)

REM Check if Node.js is available
echo [2/5] Checking Node.js installation...
node --version >nul 2>&1
if errorlevel 1 (
  echo Node.js not found. Please install Node.js 18+ and try again.
  pause
  exit /b 1
)

REM Install Python dependencies
echo [3/5] Installing Python dependencies...
if exist requirements.txt (
  pip install -r requirements.txt
  if errorlevel 1 (
    echo Failed to install Python dependencies.
    pause
    exit /b 1
  )
) else (
  echo requirements.txt not found, skipping Python deps.
)

REM Install Node.js dependencies
echo [4/5] Installing Node.js dependencies...
if exist web\package.json (
  cd web
  call npm install
  if errorlevel 1 (
    echo Failed to install Node.js dependencies.
    pause
    exit /b 1
  )
  cd ..
) else (
  echo web\package.json not found, skipping Node.js deps.
  pause
  exit /b 1
)

echo.
echo [5/5] Starting services...
echo.

REM Start API in background
echo Starting API server on http://localhost:8000 ...
start "ZODEL API" cmd /k "python main.py"

REM Wait a bit for API to start
timeout /t 3 /nobreak >nul

REM Start Web in background
echo Starting Web UI on http://localhost:3000 ...
cd web
start "ZODEL Web" cmd /k "npm run dev"

echo.
echo ==============================
echo  ZODEL should now be running:
echo    API:   http://localhost:8000
echo    WebUI: http://localhost:3000
echo.
echo  Two new windows have opened:
echo    - ZODEL API (Python backend)
echo    - ZODEL Web (Next.js frontend)
echo.
echo  Close these windows or press Ctrl+C in each to stop.
echo ==============================

pause
goto END

:END
endlocal
