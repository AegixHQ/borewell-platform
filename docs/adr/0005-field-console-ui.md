# ADR-0005: "Field Console" UI for web-app, with routing, maps and shared design tokens

**Status:** Accepted (client-approved design direction)
**Date:** 2026-09-17
**Supersedes:** nothing; extends ADR-0002 (one unified frontend app)

> **Import note (this repo):** this ADR came from the separate web/mobile
> frontend repo. Only the **native app** (`apps/borewell-native`) and the
> `0003_resource_owner_role` migration were imported here. Decisions 1-6
> and the "Context" describe `apps/web-app` / `apps/shared-ui` work
> (`tokens.js`, `src/pages/`, routing, Leaflet) that does **not** exist in
> this repo - `apps/web-app` here is still the dashboards-based reference
> client. The "Addendum" section is the part that applies to this repo.

## Context

`apps/web-app` was wired to the real backend but had no design: three
dashboard files, ~115 inline styles, no navigation, no URL routing, no
visual language. `docs/Borewell_04_UIUX.md` describes principles (depth
range always visible with a confidence badge, inline validation,
consequential actions confirmed) but no concrete system - it explicitly
defers exact colours and tokens to a "Phase-1 design-system task".

Two directions were designed and shown to the client. The approved one
("Field Console") is a graphite + saffron scheme with top pill navigation,
bold figures, dark summary cards and a vertical depth-gauge motif, chosen
over a lighter earth-toned alternative for readability outdoors and a more
product-like feel.

## Decision

1. **Design tokens live in `apps/shared-ui/src/tokens.js`**, alongside the
   domain display helpers that belong with them (stage labels, the 14→6
   phase grouping, the 14→5 customer step grouping, INR formatting, job and
   resource type labels). Plain JS, no React and no `import.meta`, so the
   file can be hand-copied into `apps/borewell-native` the same way
   `services/platform.js` already is (that app is deliberately outside the
   npm workspace - see its `AGENTS.md`).

2. **`apps/web-app` gets real URL routing** (`react-router-dom`), replacing
   state-based view switching. `nginx.conf` already had the SPA fallback
   for exactly this. Roles map to route groups: `/customer/*`,
   `/contractor/*`, `/owner/*`. Client-side role checks remain
   presentation only - every service still enforces `require_role()`
   server-side, which is what a tampered token actually hits.

3. **Screens replace the three dashboard files.** `src/pages/<role>/*`
   holds one file per screen, `src/components/*` the shared UI, `src/lib/*`
   session, data-loading and the Razorpay loader. The old
   `src/dashboards/*.jsx` are deleted rather than kept: they were the
   working reference for the API call sequences, and those sequences are
   now in the pages (git history keeps the originals).

4. **Leaflet + OpenStreetMap tiles for location picking.** Jobs and
   resources only carry lat/lng, and picking a site on a map is the whole
   point of the request flow. No API key, no account, MIT licensed.

5. **Data loading stays `fetch` + component state** (`useLoad` in
   `src/lib/hooks.js`), per Architecture §3. Because the backend has no
   notifications, screens that show someone else's action (a quote landing,
   an owner accepting) poll on a 15-30 s interval. That is a deliberate
   stopgap, documented here so it is replaced rather than copied when
   notifications exist.

6. **Payments open Razorpay Checkout from the browser** using the order and
   public key created by `POST /v1/payments/{id}/create-order`. The UI never
   treats the checkout callback as proof of payment - it re-reads the
   payment record, which only the signed webhook can move to `completed`.
   When Razorpay keys are missing the API returns 502 and the customer sees
   a plain explanation instead of a raw error.

## Consequences

- Two new runtime dependencies in `web-app`: `react-router-dom` and
  `leaflet`. Both are in the lockfile and covered by the existing frontend
  CI (`npm run lint`, `npm run build --workspace=web-app`).
- `apps/AGENTS.md` and `apps/borewell-native/AGENTS.md` referred to
  `web-app/src/dashboards/*` as the reference implementation; both now
  point at `src/pages/`.
- The native app should port these screens and copy `tokens.js` rather than
  inventing a second visual language.

## Data gaps this surfaced (not fixed here)

These are UI-visible consequences of the current API, listed so they are
decided rather than worked around silently:

1. **No names anywhere.** Jobs and bookings carry only UUIDs, and there is
   no `GET /v1/users/{id}`. Screens show a short job id and the service-area
   name; a contractor cannot see who the customer is, and an owner cannot
   see which contractor is asking.
2. **`POST /v1/resources/match` returns no lat/lng**, only `distance_km`, so
   nearby rigs cannot be drawn on the map - the search is a ranked list.
3. **Jobs have no address.** `GET /v1/service-areas/lookup` is used as the
   human-readable place name, which returns nothing outside the pilot areas.
4. **No notifications endpoint** - hence the polling above.
5. **`GET /v1/analytics/estimate-accuracy` is declared but not implemented**,
   so quoted-vs-actual is shown per job only, not aggregated (US-11).

Separately, wiring these screens against a real Postgres database exposed a
migration gap fixed in this change: the `user_role` enum never had
`resource_owner` added (migration `0003_resource_owner_role.py`), so rig
owners could not register at all outside the SQLite-backed tests.

---

## Addendum: the same design on the native app (`apps/borewell-native`)

The Expo app now carries the same screens. It follows every decision above -
the 14-stage rail for contractors, the 5 customer steps, the depth gauge on
every quotation view, the same tokens hand-copied to
`apps/borewell-native/theme.js` - with these native-specific ones:

1. **Zero new dependencies.** The app ships with `expo`, `expo-secure-store`,
   `expo-status-bar` and React; `@react-native-picker/picker` was dropped
   because nothing uses it any more. Every UI primitive that would normally
   be a package is drawn from core React Native instead:

   | Usual choice | What is here instead | Why |
   |---|---|---|
   | `react-navigation` | `lib/nav.js`, a ~90-line stack + a tab bar | Needs `react-native-screens` and `react-native-safe-area-context`, both native modules |
   | `react-native-svg` | `Icon` in `components/ui.js`, View geometry | Native module, version must match the SDK |
   | `react-native-maps` | `components/SiteMap.js`, OSM raster tiles as `<Image>`s on a Web-Mercator grid | Native module, needs a Google Maps key on Android, and cannot run in Expo Go |
   | `react-native-razorpay` / `react-native-webview` | see gap 1 below | Native modules |

   The honest reason behind all four: the Expo/npm version-resolution API was
   unreachable from the machine this was built on, so no version could be
   checked against SDK 57. Guessing one would have handed over an app that
   might not build. The cost of the choice is listed under each file's
   header; each is a contained swap later.

2. **Web preview is a supported way to run it.** `react-native-web`,
   `react-dom` and `@expo/metro-runtime` are the only additions to
   `package.json`, and they buy `npm run web` - the app in a browser, no
   phone, no simulator, no Android SDK. That is how the screens in this repo
   were verified.

3. **Demo mode by default when no backend is configured.**
   `services/demo.js` is a hand-port of `apps/web-app/src/demo/mockApi.js`
   and patches `global.fetch`. It is on when `EXPO_PUBLIC_DEMO=1` **or** when
   no `EXPO_PUBLIC_PLATFORM_SPINE_URL` is set - because the fallback
   (`localhost`) cannot reach a backend from a phone anyway, so the
   alternative first-run experience is a connection error. Every screen shows
   a DEMO chip while it is on.

4. **The session is persisted** in `expo-secure-store`, unlike the web app,
   which keeps it in `localStorage` per tab. A phone app that asks for a
   password on every cold start is a worse trade than the web one.

5. **Polling pauses in the background** (`lib/hooks.js`) and resumes with one
   immediate fetch, instead of polling four services from a pocket.

6. **Pricing and service areas are one screen** (`screens/contractor/Setup.js`)
   with a segmented control; they are two pages on the web app. A five-item
   phone tab bar has no room for both, and both are set-up-once work.

### Native gaps, on top of the API gaps above

1. **Razorpay Checkout does not open in the app.** The order is really
   created (`POST /v1/payments/{id}/create-order`), and because only the
   signed webhook can complete a payment, one paid on the web app shows as
   Paid here by itself. Finishing it is `npx expo install react-native-webview`
   plus the `unsupported` branch in `lib/checkout.js`.
2. **No "use my current location"** - that is `expo-location`, one install
   and one handler in `screens/customer/NewRequest.js`. The map opens over
   the first pilot area instead.
3. **Archivo and IBM Plex Mono are not loaded** - webfonts need
   `expo-font` plus the files, so the platform faces carry the weight.
   `theme.js` names this.
4. **OSM's public tile server** is fine for a pilot but its usage policy
   wants an identifying User-Agent that `<Image>` cannot set. `TILE_URL` in
   `components/SiteMap.js` is one line to repoint.
