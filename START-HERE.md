# Borewell demo - run it on your computer

This starts the whole system locally: four backend services with their
databases, and the mobile app running in your browser. Nothing is sent
anywhere. It is for demos only (development passwords, no HTTPS, no real
payments).

## You need

1. **Docker Desktop**, installed and **running** (docker.com). Windows, Mac or Linux.
2. **Node.js 20 or newer** (nodejs.org).
3. About 5 GB free disk and an internet connection for the first start.

## Start it

**Windows:** double-click `start-demo.bat`
**Mac / Linux:** open a terminal in this folder and run `./start-demo.sh`

The first run builds everything and takes a few minutes. When it finishes it
prints a link, usually **http://localhost:8081**. Open it in Chrome. Press F12,
then the phone icon (device toolbar), to see it phone-shaped.

## Log in (password for all three: `demo-password-123`)

| Role | Email | What you can show |
|---|---|---|
| Customer | customer@example.com | Request a borewell, see a quote, approve it |
| Contractor | contractor@example.com | Job board, generate a quotation, find nearby rigs, advance a job |
| Rig owner | owner@example.com | List a rig, accept or decline booking requests |

You can also tap **Create account** to make your own.

## Suggested 3-minute walkthrough

1. **Customer:** Request, drag the map pin near Virudhunagar or Madurai, pick a type, send.
2. **Contractor:** open that job, Generate quotation (shows a depth range and confidence), then Find nearby rigs and send a booking request.
3. **Rig owner:** Requests, accept it.
4. **Customer:** open the job, approve the quotation.
5. **Contractor:** advance the job through the stages.

Payment cannot be completed in this demo build (it needs live Razorpay keys).

## Stop it

**Windows:** double-click `stop-demo.bat`. **Mac / Linux:** `./stop-demo.sh`.
This also deletes the demo data; the next start begins fresh.

## Something wrong?

- *"Docker is not running"*: open Docker Desktop and wait until it says it is running.
- *Page says "Failed to fetch" or shows no data*: the backend is not up yet. Wait a minute, check `docker compose ps`, reload.
- *"Failed to fetch" only after login attempts*: the app must run on port **8081** (the backend only allows that address). If it says 8081 is busy, close the other program and start again.
- *Port already in use* (8001-8004, 8081, 5432-ish): close whatever uses it, or run `stop-demo` first.
- *Logs*: `docker compose logs -f`.

## No Docker? (Mac / Linux, Python 3.11+ and Node)

```bash
./run-local.sh                          # backend on SQLite + the web dashboard
python3 tools/seed-demo/seed_demo.py    # demo accounts and data (in a second terminal)
cd apps/borewell-native && cp .env.example .env   # set the four URLs to http://localhost:8001..8004
npm install && npx expo start --web --port 8081
```

## Just look at the app, no backend at all

```bash
cd apps/borewell-native && npm install && npm run web
```

Delete the `.env` file first if one exists. Every screen shows a small DEMO
chip and uses built-in sample data.
