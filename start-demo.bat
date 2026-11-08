@echo off
rem Starts the Borewell demo in your browser. Needs Node.js 20+ only.
rem No Docker, no database, no backend: the app runs on built-in sample data.
cd /d "%~dp0apps\borewell-native" || exit /b 1
where node >nul 2>nul || (echo Node.js is not installed. Get it from nodejs.org ^(version 20 or newer^), then run this again. & pause & exit /b 1)
if not exist node_modules (
  echo First run: installing ^(a minute or two^)...
  call npm install --no-audit --no-fund || (pause & exit /b 1)
)
set EXPO_PUBLIC_DEMO=1
echo Starting... the browser opens by itself. Sign in as Customer, Contractor or Rig owner with any password.
echo Close this window or press Ctrl+C to stop.
call npx expo start --web --port 8081
