@echo off
rem One-command demo (Windows). Needs Docker Desktop running, and Node 20+. See START-HERE.md.
cd /d "%~dp0"

where docker >nul 2>nul || (echo Docker is not installed. Install Docker Desktop first. & pause & exit /b 1)
docker info >nul 2>nul || (echo Docker is installed but not running. Start Docker Desktop and retry. & pause & exit /b 1)

echo 1/3 Starting the backend (first run takes a few minutes to build)...
docker compose up --build -d postgres-platform-spine postgres-quotation postgres-resource-network postgres-payments-data redis platform-spine quotation resource-network payments-data
if errorlevel 1 (echo Backend failed to start. & pause & exit /b 1)

echo 2/3 Loading demo data...
docker compose exec -T -e PLATFORM_SPINE_URL=http://localhost:8000 -e QUOTATION_URL=http://quotation:8000 -e RESOURCE_NETWORK_URL=http://resource-network:8000 platform-spine python - < tools\seed-demo\seed_demo.py
if errorlevel 1 echo Demo data was not loaded. The app still works: use Create account.

echo 3/3 Starting the app...
cd apps\borewell-native
if not exist .env (
  > .env echo EXPO_PUBLIC_PLATFORM_SPINE_URL=http://localhost:8001
  >> .env echo EXPO_PUBLIC_QUOTATION_URL=http://localhost:8002
  >> .env echo EXPO_PUBLIC_RESOURCE_NETWORK_URL=http://localhost:8003
  >> .env echo EXPO_PUBLIC_PAYMENTS_URL=http://localhost:8004
)
where node >nul 2>nul || (echo Backend is running. Install Node.js 20+ from nodejs.org, then run this again. & pause & exit /b 0)
if not exist node_modules call npm install --no-audit --no-fund
echo Open the URL it prints (usually http://localhost:8081).
echo Sign in with customer@example.com, contractor@example.com or owner@example.com - password demo-password-123
call npx expo start --web --port 8081
