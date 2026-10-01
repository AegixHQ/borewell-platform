# Running the whole thing on your phone (Windows, no Docker)

Backend on your PC, app on your phone, over your Wi-Fi. **No Docker, no
Postgres, no Redis** — the four services run straight from Python against
SQLite files.

Every command below was run end to end before it was written down: the four
services start, a customer registers, a contractor quotes, an owner accepts
a rig booking, the customer approves and a payment row is created — and the
app itself was driven against that exact stack.

**You need:** Python 3.11+ (`python --version`), Node.js 20+
(`node --version`), and **Expo Go** installed on the phone.

---

## 1. One-time setup

Open the repo folder in VS Code → Terminal → New Terminal (PowerShell), at
the repo root:

```powershell
# a virtual environment for the backend
python -m venv .venv

# install what all four services need (no psycopg2 - that's Postgres only)
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install "fastapi>=0.110" "uvicorn[standard]>=0.29" "sqlalchemy>=2.0" "alembic>=1.13" "pydantic>=2.6" "redis>=5.0" "pyjwt>=2.8" "bcrypt>=4.1" "email-validator>=2.1" "httpx>=0.27"
```

Then create each service's database. Still the same terminal:

```powershell
$env:JWT_SECRET = "dev-secret-change-me-at-least-32-characters-long"
$env:DATABASE_URL = "sqlite:///./dev.db"

cd services\platform-spine   ; ..\..\.venv\Scripts\python.exe -m alembic upgrade head ; cd ..\..
cd services\quotation        ; ..\..\.venv\Scripts\python.exe -m alembic upgrade head ; cd ..\..
cd services\resource-network ; ..\..\.venv\Scripts\python.exe -m alembic upgrade head ; cd ..\..
cd services\payments-data    ; ..\..\.venv\Scripts\python.exe -m alembic upgrade head ; cd ..\..
```

Each service gets its own `dev.db` inside its own folder — four separate
databases, exactly like the four separate Postgres containers.

Finally, let the phone through the Windows firewall. **Run PowerShell as
Administrator** once:

```powershell
New-NetFirewallRule -DisplayName "Borewell dev" -Direction Inbound -Protocol TCP -LocalPort 8001-8004,8081 -Action Allow -Profile Private
```

---

## 2. Start the backend — four terminals

In VS Code, click the **+** in the terminal panel for each one. They all
stay running; `Ctrl+C` stops one.

**⚠️ `JWT_SECRET` must be the *same string* in all four** — every service
verifies tokens issued by `platform-spine`. A mismatch shows up as 401s on
every screen after a successful login.

**Terminal 1 — platform-spine (8001)**

```powershell
cd services\platform-spine
$env:JWT_SECRET = "dev-secret-change-me-at-least-32-characters-long"
$env:DATABASE_URL = "sqlite:///./dev.db"
$env:QUOTATION_SERVICE_URL = "http://127.0.0.1:8002"
..\..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8001
```

**Terminal 2 — quotation (8002)**

```powershell
cd services\quotation
$env:JWT_SECRET = "dev-secret-change-me-at-least-32-characters-long"
$env:DATABASE_URL = "sqlite:///./dev.db"
$env:PLATFORM_SPINE_URL = "http://127.0.0.1:8001"
$env:RESOURCE_NETWORK_URL = "http://127.0.0.1:8003"
..\..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8002
```

**Terminal 3 — resource-network (8003)**

```powershell
cd services\resource-network
$env:JWT_SECRET = "dev-secret-change-me-at-least-32-characters-long"
$env:DATABASE_URL = "sqlite:///./dev.db"
..\..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8003
```

**Terminal 4 — payments-data (8004)**

```powershell
cd services\payments-data
$env:JWT_SECRET = "dev-secret-change-me-at-least-32-characters-long"
$env:DATABASE_URL = "sqlite:///./dev.db"
$env:QUOTATION_SERVICE_URL = "http://127.0.0.1:8002"
..\..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8004
```

`--host 0.0.0.0` is what lets the phone reach them. Without it they only
answer to the PC itself.

Check all four from a fifth terminal:

```powershell
curl http://localhost:8001/healthz
curl http://localhost:8002/healthz
curl http://localhost:8003/healthz
curl http://localhost:8004/healthz
```

Each should print `{"status":"ok"}`.

---

## 3. Point the app at your PC

Find your PC's LAN address:

```powershell
ipconfig
```

Take the **IPv4 Address** of your active Wi-Fi adapter — something like
`192.168.1.50`. Not `127.0.0.1`, not the 169.254.x.x one.

```powershell
cd apps\borewell-native
copy .env.example .env
notepad .env
```

Put this in it, with your own IP:

```
EXPO_PUBLIC_DEMO=0
EXPO_PUBLIC_PLATFORM_SPINE_URL=http://192.168.1.50:8001
EXPO_PUBLIC_QUOTATION_URL=http://192.168.1.50:8002
EXPO_PUBLIC_RESOURCE_NETWORK_URL=http://192.168.1.50:8003
EXPO_PUBLIC_PAYMENTS_URL=http://192.168.1.50:8004
```

`EXPO_PUBLIC_DEMO=0` is what switches off the built-in fake backend. If you
leave the DEMO chip showing in the app, the `.env` isn't being read —
restart Expo, the values are baked in at start.

## 4. Start the app

```powershell
cd apps\borewell-native
npm install          # first time only
npm start
```

A QR code appears. **Android:** open Expo Go → *Scan QR code*.
**iPhone:** open the Camera app, point it at the QR, tap the banner.

The phone and the PC must be on the **same Wi-Fi**, and it must not be a
guest network with client isolation. If Metro won't connect at all:

```powershell
npx expo start --tunnel
```

That routes through Expo's servers — slower, but it works across networks.
Note the backend URLs in `.env` still have to be reachable from the phone,
so a tunnel doesn't help if the phone can't reach your PC's IP.

---

## 5. First five minutes in the app

The database starts empty, so create data in this order — otherwise screens
look broken when they're just empty:

1. **Register a rig owner** → **Fleet** → *List equipment*: name it, set an
   hourly rate, drag the map to place it. Only *available* listings with a
   location are searchable.
2. **Sign out. Register a contractor** → **Setup → Pricing**: fill in every
   field for one job type and save. **No quotation can be generated without
   this** — you'll get "Set your pricing rule…" otherwise.
   → **Setup → Service areas**: add e.g. Kallikudi, water depth 440 ft. This
   is what makes a quote location-aware instead of using your flat guess.
3. **Sign out. Register a customer** → **Request**: drag the map, pick a
   type, *Get my estimate*.
4. **Contractor** → open the job → **Generate quotation** → **Find nearby
   rigs** → send a booking request.
5. **Owner** → accept it.
6. **Customer** → approve the quotation.
7. **Contractor** → **Advance stage** until Completion → record the actual
   depth and cost to see the variance.

Two phones (or a phone + the browser via `npm run web`) make this much
less tedious than signing in and out.

---

## Troubleshooting

| What you see | What it is |
|---|---|
| App shows the **DEMO** chip | `.env` not read, or `EXPO_PUBLIC_DEMO` isn't `0`. Restart Expo after editing it. |
| "Network request failed" on sign-in | Phone can't reach the PC: wrong IP, firewall rule missing, different Wi-Fi, or a service not started with `--host 0.0.0.0`. |
| Login works, then every screen 401s | `JWT_SECRET` differs between terminals. It must be the same string in all four. |
| "Set your pricing rule…" when quoting | Step 2 above — the quotation service refuses to invent prices. |
| Payment says the sheet can't open | Known gap: Razorpay Checkout needs a native module that isn't installed. The order is created for real; see `apps/borewell-native/lib/checkout.js`. |
| Map is blank grey | Tiles come from OpenStreetMap over the internet — the phone needs a working connection, and they fade in a second late. |
| Names are missing everywhere | The API carries only IDs; there is no users endpoint yet. Screens show a job code and the village name instead. |

## Resetting

Stop the four terminals and delete the four `dev.db` files:

```powershell
del services\platform-spine\dev.db, services\quotation\dev.db, services\resource-network\dev.db, services\payments-data\dev.db
```

Then re-run the `alembic upgrade head` block from step 1.

---

## One caveat worth knowing

SQLite is not what this runs on in production — Postgres is. They differ,
and that difference has already bitten this project once: rig owners
couldn't register at all on Postgres because the `user_role` enum was
missing a value, and every SQLite-backed test passed anyway (fixed in
migration `0003_resource_owner_role.py`). SQLite is the right call for
getting the app onto your phone today; it is not a substitute for testing
against Postgres before launch.
