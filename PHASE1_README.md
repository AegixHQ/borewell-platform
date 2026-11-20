# Borewell Phase 1 native API resilience patch

This patch is deliberately limited to the Android/Expo app's API transport, user-facing errors, refresh behaviour, and automated checks. It does not change backend services, database schemas, production configuration, payment logic, or deployment state.

## Where to apply it

Apply this only in a development clone of `AegixHQ/borewell-platform` on your workstation (not in `~/borewell-platform` on the production VM).

The VM checkout reported commit `266aca3`; GitHub `main` has two newer commits that only change the APK build workflow. Start from current GitHub `main` so the patch anchors match.

```bash
git clone https://github.com/AegixHQ/borewell-platform.git
cd borewell-platform
git switch main
git pull --ff-only origin main
```

Download `phase1_native_api_resilience.py` into this repository root, then run:

```bash
python3 phase1_native_api_resilience.py
```

The script:
- requires a clean working tree;
- creates `phase1/native-api-resilience` from `main`;
- validates every replacement anchor before writing files;
- refuses to overwrite an existing file with different content;
- does not deploy, modify `.env.prod`, access a database, or build an APK.

If an anchor does not match, it exits before writing any files. It is safe to update the clone and rerun after inspecting the cause.

## What it changes

- Adds a single native JSON API transport shared by platform calls and password/Google authentication.
- Adds a 15-second request timeout and structured errors (HTTP status, server code, trace ID, `Retry-After`).
- Retries only safe GET requests once on network/timeout and transient 408/502/503/504 failures. It does not auto-retry POST/PATCH/PUT/DELETE operations, including payments and bookings, and does not auto-retry 429 responses.
- Preserves previously loaded data when refreshes fail, ignores stale out-of-order load results, and adds a reusable retry notice.
- Adds client-side email, phone, and password checks aligned with the current platform-spine registration schema.
- Adds dependency-free Node tests and runs them in native-app CI.
- Sets `EXPO_PUBLIC_USE_RN_FETCH=1` in the APK build workflow. Expo SDK 57 otherwise installs `expo/fetch` as the native global `fetch`; this setting keeps React Native's built-in fetch for the timeout-based transport.

No new runtime or development dependency is added.

## Validate the branch

```bash
cd apps/borewell-native
npm ci
npm test
npm run lint
npm run bundle-check
```

Only the new transport's six Node tests were executed while preparing this patch; they passed. The full app lint and Metro bundle checks have **not** been run here because the connected GitHub integration is read-only and this environment does not have the complete repository checkout. Run the commands above before pushing.

If all checks pass:

```bash
git status --short
git diff --check
git diff --stat
git add apps/borewell-native .github/workflows/ci-borewell-native.yml .github/workflows/build-demo-apk.yml
git commit -m "Improve native API error handling and resilient loading"
git push -u origin phase1/native-api-resilience
```

Open a PR into `main`; do not merge until CI is green.

## OpenStreetMap is a separate unresolved item

This patch does **not** claim to fix the OSM tiles. Phase 0 reproduced the difference: Android Chrome displayed the tile, the Borewell APK displayed an OSM blocked tile, while the VM's curl got HTTP 200. The current map already uses React Native Image `source.headers` with a Borewell User-Agent, and React Native documents those headers as supported. Therefore the next map change should first instrument an actual native request and compare its status/content headers with the image request, then detect a policy-warning image response and switch providers; `onError` alone is insufficient for an HTTP-200 warning image.

The OSMF tile policy requires a stable app-specific User-Agent for native apps, requires cache-respecting tile use, does not normally require Referer for native apps, and provides best-effort service without an SLA. Do not add no-cache headers, bulk-prefetch tiles, or use an arbitrary public tile host as a production workaround. Use a provider whose commercial terms and quota fit the app if the public OSM tile service is not suitable.
