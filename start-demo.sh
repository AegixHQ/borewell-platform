#!/usr/bin/env bash
# Starts the Borewell demo in your browser. Needs Node.js 20+ only.
# No Docker, no database, no backend: the app runs on built-in sample data.
cd "$(dirname "$0")/apps/borewell-native" || exit 1
command -v node >/dev/null || { echo "Node.js is not installed. Get it from nodejs.org (version 20 or newer), then run this again."; exit 1; }
[ -d node_modules ] || { echo "First run: installing (a minute or two)..."; npm install --no-audit --no-fund || exit 1; }
export EXPO_PUBLIC_DEMO=1
echo "Starting... the browser opens by itself. Sign in as Customer, Contractor or Rig owner with any password."
echo "Press Ctrl+C here to stop."
npx expo start --web --port 8081
