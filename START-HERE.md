# Borewell demo - run it in your browser

Runs the Borewell mobile app in your web browser on built-in sample data.
No Docker, no database, no backend, no account setup. Nothing leaves your
computer, and nothing is saved: reloading the page resets the demo.

## You need

**Node.js 20 or newer** (free, from nodejs.org). That is all.

## Start it

- **Windows:** double-click `start-demo.bat`
- **Mac / Linux:** open a terminal in this folder and run `./start-demo.sh`

The first run installs things (a minute or two), then your browser opens at
**http://localhost:8081**. Press **F12**, then the phone icon, to see it
phone-shaped. Press **Ctrl+C** in the terminal (or close the window) to stop.

## Use it

On the sign-in screen, tap **Customer**, **Contractor** or **Rig owner**
under "Demo mode", then tap **Sign in** (any password).

| Role | What you can show |
|---|---|
| Customer | Request a borewell, see the quote and depth range, approve it |
| Contractor | Job board, quotation, find nearby rigs, advance a job through its stages |
| Rig owner | List a rig, accept or decline booking requests |

Every screen shows a small **DEMO** chip while this mode is on.

## If something goes wrong

- *"Node.js is not installed"*: install it from nodejs.org, then run the start file again.
- *Browser did not open*: go to http://localhost:8081 yourself.
- *Port 8081 is busy*: close the other program and start again.
- *Install fails*: check the internet connection and run the start file again.

## Optional: with the real backend (Mac / Linux, Python 3.11+)

The demo above does not use the backend. To run the real four services too:

```bash
./run-local.sh                          # backend on SQLite (leave running)
python3 tools/seed-demo/seed_demo.py    # second terminal: demo accounts and data
cd apps/borewell-native && cp .env.example .env   # set the four URLs to http://localhost:8001 .. 8004
npm install && npx expo start --web --port 8081
```

Then sign in with `customer@example.com`, `contractor@example.com` or
`owner@example.com`, password `demo-password-123`. Docker is another option; see `README.md`.
