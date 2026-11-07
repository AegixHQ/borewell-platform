# Running this locally (Windows + VS Code)

This repo is the **backend** (4 services) plus the **mobile app**
(`apps/borewell-native`). The web frontend is in its own repo, against this
same backend.

## Option 0 — just look at the app (no Docker, no database)

Needs only **Node.js 20+**.

```powershell
cd apps\borewell-native
npm install
npm run web
```

Open the URL it prints and make the window phone-shaped. Sign in as
**Customer**, **Contractor** or **Rig owner** — any password.

With no `.env` file the app runs against an in-memory backend seeded with
jobs, quotes, rigs and booking requests, so every screen works and the whole
flow clicks through. Nothing is saved: reload and it starts fresh. Every
screen shows a small **DEMO** chip while this is on.

**On a real phone:** install **Expo Go** from the App Store or Play Store,
run `npm start` instead, and scan the QR code. Phone and PC must be on the
same Wi-Fi.

---

## Option A2 — the real backend with **no Docker at all**

If Docker won't run on your machine (virtualization disabled, Windows Home,
a locked-down laptop), the four services run straight from Python against
SQLite files instead. That is the fastest route to the app on a real phone:
see **[RUN-ON-PHONE.md](RUN-ON-PHONE.md)** — every command in it was run end
to end before it was written.

## Option A — the real backend, everything in Docker

**Needs:** Docker Desktop running.

```powershell
# 1. Open this folder in VS Code, Terminal -> New Terminal
code .

# 2. Create the one required secret
copy services\platform-spine\.env.example services\platform-spine\.env
#    open that file and set JWT_SECRET to any long random string

# 3. Build and start the backend (first run pulls images - a few minutes)
docker compose up --build -d

# 4. Check the four services answer
curl http://localhost:8001/healthz
curl http://localhost:8002/healthz
curl http://localhost:8003/healthz
curl http://localhost:8004/healthz
```

Each service runs its own migrations on start, so there is no separate
migrate step.

```powershell
docker compose logs -f     # follow logs (Ctrl+C stops following)
docker compose down        # stop everything
docker compose down -v     # stop and wipe the databases
```

## Option B — point the app at that backend

```powershell
cd apps\borewell-native
copy .env.example .env
```

Put your PC's **LAN IP** in that file — `ipconfig`, the IPv4 address, e.g.
`192.168.1.50`. Not `localhost`: on a phone, `localhost` means the phone.

```
EXPO_PUBLIC_PLATFORM_SPINE_URL=http://192.168.1.50:8001
EXPO_PUBLIC_QUOTATION_URL=http://192.168.1.50:8002
EXPO_PUBLIC_RESOURCE_NETWORK_URL=http://192.168.1.50:8003
EXPO_PUBLIC_PAYMENTS_URL=http://192.168.1.50:8004
```

Then `npm start` and open it in Expo Go. Restart Expo after editing `.env` —
the values are inlined at build time. `EXPO_PUBLIC_DEMO=1` forces demo mode
back on; `EXPO_PUBLIC_DEMO=0` forces the real services.

If the app can't reach the backend from the phone, it is almost always one
of three things: wrong IP, the PC's firewall blocking ports 8001–8004, or
the phone being on a different network (guest Wi-Fi, or mobile data).

---

## First five minutes with a real backend

The backend starts empty, so create the data in this order:

1. **Register a rig owner** → Fleet → **List equipment**: name it, set an
   hourly rate, drag the map to place it. Only *available* listings with a
   location are searchable.
2. **Register a contractor** (a second phone, or sign out and back in) →
   **Setup → Pricing**: fill in one job type and save. No quote can be
   generated without this. → **Setup → Service areas**: add a village with a
   water depth, e.g. Kallikudi at 440 ft.
3. **Register a customer** → **Request**: drag the map, pick a type, submit.
4. **Contractor** → open the job → **Generate quotation** → **Find nearby
   rigs** → send a booking request.
5. **Owner** → accept the request.
6. **Customer** → approve the quotation.
7. **Contractor** → **Advance stage** until Completion → record the actual
   depth and cost to see the variance.

## Three things that will look broken but aren't

- **Payment can't be completed from the app.** The order is created for
  real, but opening Razorpay's checkout sheet needs a native module that
  isn't installed (see `apps/borewell-native/lib/checkout.js`). A payment
  completed elsewhere shows as Paid in the app on its own, because only
  Razorpay's signed webhook can complete one. Razorpay also needs
  `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET` and `RAZORPAY_WEBHOOK_SECRET` in
  `services\payments-data\.env`; without them the API returns 502 and the
  app shows a plain explanation.
- **Names are missing everywhere.** Jobs and bookings carry only IDs — there
  is no users endpoint yet — so screens show a short job code and the
  service-area name instead of a person's name.
- **The map is grey at first.** Tiles load from OpenStreetMap over the
  network; on a slow connection they fade in a moment later.

## Checks before committing

```powershell
cd apps\borewell-native
npm run lint
npm run bundle-check          # Metro bundles the app for a real iOS target

# from each services\<name> folder:
python -m pytest
# from the repo root:
ruff check services\
python tools\contract-check\check_contract.py platform-spine
```

## Where the app's code lives

```
apps/borewell-native/theme.js      colours, type, stage labels, INR format
apps/borewell-native/services/     API client, auth, the demo backend
apps/borewell-native/lib/          session, data loading, navigation, checkout
apps/borewell-native/components/   UI kit, depth gauge, tile map, stage rail
apps/borewell-native/screens/      one file per screen, grouped by role
apps/borewell-native/AGENTS.md     conventions, and what has actually been run
docs/adr/0005-field-console-ui.md  why it looks the way it does, and the API gaps
```
