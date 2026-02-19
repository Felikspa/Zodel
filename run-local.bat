@echo off
setlocal

echo ==============================
echo  ZODEL Local run script
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
endlocal
