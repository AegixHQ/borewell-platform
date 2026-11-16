# Expo HAS CHANGED

Read the exact versioned docs at https://docs.expo.dev/versions/v57.0.0/
before writing any code.

---

# This app, specifically

The React Native/Expo app, built to the approved "Field Console" design
(`docs/adr/0005-field-console-ui.md`, including its native addendum).
`apps/web-app/src/dashboards/*.jsx` remains a reference for API call
sequences, but **web-app has not been restyled in this repo** - ADR-0005's
web-app sections describe work that lives in the separate web repo. Until
that lands here, this app is the only place the design tokens exist.

**Read the root `AGENTS.md` and `STRUCTURE.md` first** - this app follows
the same contract-first discipline as the rest of the repo.
`packages/contracts/openapi/*.yaml` is the source of truth for every
request/response shape any screen here uses.

## Layout

```
theme.js                 design tokens (apps/shared-ui/src/tokens.js does not exist in this repo yet)
services/platform.js     API client   ) hand-copied from shared-ui, see
services/auth.js         login/JWT    ) each file's header
services/demo.js         in-memory backend (originally ported from web-app's mockApi.js, which is not in this repo)
lib/session.js           session + expo-secure-store persistence
lib/hooks.js             useLoad / useAction / useToast / useAreaName
lib/nav.js               the stack navigator (90 lines, no dependency)
lib/razorpay.js          Razorpay Checkout options + the HTML the native WebView loads
lib/google.js            Google sign-in (native module; lib/google.web.js is a no-op)
components/ui.js         buttons, cards, badges, pills, sheets, icons
components/SiteMap.js    OSM tile map (sends the User-Agent/Referer OSM requires; falls back to CARTO), no native module
components/RazorpaySheet.js  Razorpay Checkout in a WebView (.web.js loads checkout.js directly)
components/DepthGauge.js the depth ruler, in Views rather than SVG
components/StageViews.js the 14-stage rail and the 5 customer steps
components/AppShell.js   top bar, page header, tab bar
screens/contractor/WalkIn.js  "New walk-in job" for a customer with no account (see docs/BACKEND_INTEGRATION.md)
screens/index.js         route table + the tabs each role gets
screens/**               one file per screen, grouped by role
```

## Rules specific to this app

- **Do not add a dependency without a reason in the PR description**, and
  prefer none: every UI primitive here is core React Native on purpose (the
  table in ADR-0005's addendum says what was skipped and why). Adding
  `react-navigation`, `react-native-svg`, `react-native-maps` or
  `react-native-webview` is a legitimate future change - but it is a native
  module, so `npx expo install <pkg>` (not `npm install`), and it takes the
  app out of Expo Go.
- **Colours, type, stage labels and INR formatting come from `theme.js`.**
  Don't hand-write a hex value or re-label a job stage in a screen. If
  a shared `tokens.js` is ever added to `apps/shared-ui`, keep the two in sync by hand -
  there is no build tooling sharing code between the Vite workspace and
  this app, which is also why this app is **deliberately excluded from the
  root npm workspace** (Metro has known issues resolving hoisted
  `node_modules`).
- **Client-side role routing is presentation only** (ADR-0002). The
  boundary is every service's `require_role()`. Role is chosen once, at
  registration; the sign-in screen must never ask for it again.
- **Screens take `params` as a prop** (`screens/index.js` maps route names
  to components) and navigate with `useNav()`'s
  `navigate` / `replace` / `reset` / `goBack`.
- **404 is a normal answer** from `GET /v1/quotations/job/{id}/latest`,
  `.../completion/result` and `/v1/service-areas/lookup`. Catch it and show
  the empty state; don't surface it as an error.
- **Money is a decimal string.** Pass `total_estimate` and `amount` back to
  the API exactly as received - `formatInr()` is for display only.

## What has actually been run

Reported honestly, per the root AGENTS.md:

- `npm run lint` - clean.
- `npm run bundle-check` - Metro bundles for iOS (569 modules) and Android (567).
- `npm run web` + a headless browser at 390x844: signed in as all three
  seeded demo accounts, walked every screen, and completed two real
  flows end to end against `services/demo.js` - customer approves a
  quotation and pays (payment reaches `completed` through the same code
  path the webhook drives), and a rig owner accepts a booking request
  (the listing flips to Reserved and drops out of the searchable count).
  No console or page errors.
- Payments in demo mode, headless: customer approves, chooses **cash**, a
  contractor confirms receipt (job shows Paid); cash declined then retried
  online; online payment through the demo backend. The real Razorpay sheet
  and Google sign-in have **not** been run - they need real credentials and a
  device. The map falls back to CARTO tiles when OpenStreetMap is blocked
  (seen in the headless browser); the OSM-with-headers path itself has not
  been seen on an Android device.
- Walk-in customers, headless against `services/demo.js`: contractor opens a
  walk-in job (form validation shown), generates the quote, taps *Customer
  agreed*, then *Record cash received* (job shows Paid, "Walk-in" badge on the
  Board); the customer account does not see the job. Not run against the real
  services from the app (the backend behaviour is covered by each service's tests).
- **Not** run on a physical device or a simulator, and not yet run against
  the real four services from a phone. The web preview exercises the same
  JavaScript, but layout on a real device, `expo-secure-store` and the
  Android back button have not been seen working. Do that before calling
  anything here field-tested.

## Native modules added for payments and Google sign-in

`react-native-webview` (hosts Razorpay's own checkout.js page, so there is no
Razorpay native SDK to build) and `@react-native-google-signin/google-signin`
(the library Expo's Google-authentication guide recommends; a browser-redirect
flow has Android custom-scheme pitfalls). Both are native, so **the app no
longer runs in Expo Go** - use a development build or the APK. `npx expo
install` could not reach Expo's API when they were added, so
`react-native-webview` was installed with `npm install` at the version in
`expo/bundledNativeModules.json`, and google-signin at 17.0.0 from npm. Run
`npx expo install --check` when you can.

## Local development

Copy `.env.example` to `.env` and use your machine's real LAN IP, not
`localhost` - see `services/platform.js`'s comment for why. With no `.env`
at all the app starts in demo mode against `services/demo.js`, which is
intentional (ADR-0005 addendum, point 3).
