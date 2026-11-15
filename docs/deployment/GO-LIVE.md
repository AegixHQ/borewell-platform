# Go live in 8 steps

You enter keys and secrets in **one file** (`.env.prod`); everything else is
generated, defaulted or checked for you. Details and background:
[PRODUCTION.md](PRODUCTION.md).

## What you need first

- A Linux server (2 vCPU / 4 GB, Ubuntu is fine) with **Docker + Docker Compose v2**, `git`, `make`, `python3`.
- A domain you control, e.g. `api.yourdomain.in`, with an **A record pointing at the server**. Open **ports 80 and 443** in the server's firewall — nothing else (`8001-8004` and Grafana stay private).
- Optional: a Razorpay account (online payments), a Google Cloud project (Google sign-in). Without them the app runs with **cash payments and email/password sign-in**.

## 1. Get the code and create `.env.prod`

```bash
git clone https://github.com/AegixHQ/borewell-platform.git && cd borewell-platform
make prod-init DOMAIN=api.yourdomain.in EMAIL=you@yourdomain.in
```

This writes `.env.prod` (mode 600) and **generates the database password, JWT secret and Grafana password**. It never overwrites an existing file.

## 2. Fill in the `>>> YOU ENTER <<<` part of `.env.prod`

| Setting | Where it comes from |
|---|---|
| `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET` | Razorpay Dashboard → Settings → API Keys. **Start with `rzp_test_` keys.** Looks like `rzp_test_AbCdEf1234GhIj` / a 24-character secret. |
| `RAZORPAY_WEBHOOK_SECRET` | Dashboard → Settings → Webhooks → Add New Webhook. URL `https://api.yourdomain.in/v1/payments/webhook`, events `payment.captured` + `payment.failed`, and a secret **you** choose (8+ chars). Paste the same secret here. |
| `GOOGLE_CLIENT_IDS` | Step 6 below. Looks like `123456789012-abcdefghijklmnopqrstuvwxyz123456.apps.googleusercontent.com`. |
| `BOOTSTRAP_ADMIN_EMAIL` / `_PASSWORD` | Your admin login (12+ char password). Delete the password line after the first deploy. |

Every variable in `.env.prod` has a comment saying what it is, where to get it, and a made-up `Example:` of the format. `make prod-check` rejects an example pasted in unchanged. Leave Razorpay or Google blank to switch that feature off. Razorpay is all-three-or-none.

## 3. Check it

```bash
make prod-check
```

Prints every mistake it can find (http origin, half-filled Razorpay, DNS not pointing yet, …) and the exact webhook URL. Fix until it says **Preflight passed**.

## 4. Deploy

```bash
make prod-deploy
```

Preflight → build → start with HTTPS (Let's Encrypt certificate is issued automatically) → smoke test from the public address (routes, TLS, HSTS, port 80 redirect, closed ports, Google/Razorpay switched on). Re-run it any time (`git pull && make prod-deploy`) to update.

If something fails: `tools/go-live/stack.sh logs --tail 100 gateway` (certificate) or `… platform-spine`. First time, you can add `LETSENCRYPT_CA_SERVER=https://acme-staging-v02.api.letsencrypt.org/directory` to `.env.prod` to avoid Let's Encrypt rate limits — phones won't trust that certificate; remove it for the real run.

## 5. Accounts

- Admin: created by step 2 on the first start. Then **delete `BOOTSTRAP_ADMIN_PASSWORD` from `.env.prod`** and `make prod-deploy` again.
- Contractor (public sign-up is closed on purpose): `make prod-contractor EMAIL=owner@yourdomain.in` (asks for a password).
- Customers and rig owners register in the app.

## 6. Google sign-in (optional)

In Google Cloud Console → APIs & Services → Credentials:
1. Configure the OAuth consent screen (External; add yourself as a test user while testing).
2. **Create OAuth client ID → Web application.** Copy the Client ID into `GOOGLE_CLIENT_IDS` in `.env.prod`, then `make prod-deploy`.
3. **Create OAuth client ID → Android**: package name `in.aegix.borewell`, SHA-1 = the one printed in the APK release notes (step 7; for CI-built APKs it is the same every time).

## 7. Build the phone app

GitHub repo → Settings → Secrets and variables → Actions → **Variables**: add `API_DOMAIN` = `api.yourdomain.in` and (if using Google) `GOOGLE_WEB_CLIENT_ID` = the *Web* client ID. Then Actions → **Build demo APK** → Run workflow (inputs can stay blank). The APK appears on a draft release; install it on an arm64 Android phone (allow "install unknown apps").

## 8. Test before real money

1. Register a customer in the app, post a job; as the contractor generate and approve a quotation.
2. Pay online with Razorpay **test** card/UPI → the job moves to the payment stage. Pay another job in **cash** → contractor taps *Cash received*.
3. Switch to `rzp_live_` keys in `.env.prod` + a live webhook in Razorpay, `make prod-deploy`, and make one small real payment.
4. Run `make prod-backup` once and schedule it: `0 2 * * * cd /path/to/borewell-platform && ./infra/backup/backup.sh` (see [infra/backup/README.md](../../infra/backup/README.md); copy backups off the server too).

## Not covered (be aware)

- **Play Store release:** the CI APK is signed with Expo's debug key — fine to install directly, not for the Play Store (needs your own upload keystore).
- Cash confirmation has no per-contractor ownership; any contractor can confirm any cash payment ([SECURITY.md](../../SECURITY.md) #10).
- Single server, no high availability; Razorpay KYC/settlement is on Razorpay's side.
- Nothing here has been exercised on a real server, a real Razorpay account or a real phone; the tooling is tested (`tools/go-live/tests`, CI), the compose files are validated, but the first live run is yours — that is what steps 4 and 8 are for.
