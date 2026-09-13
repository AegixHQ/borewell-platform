# Expo HAS CHANGED

Read the exact versioned docs at https://docs.expo.dev/versions/v57.0.0/ before writing any code.

---

# This app, specifically

React Native/Expo port of `apps/web-app`'s dashboards (see that app's own
`AGENTS.md` and `apps/web-app/src/dashboards/*.jsx` for working reference
implementations of every screen's real logic - not directly portable
JSX, but the API call sequence and state shape are exactly what each
native screen needs).

**Read the root `AGENTS.md` and `STRUCTURE.md` first** - this app follows
the same contract-first discipline as every other part of this repo.
`packages/contracts/openapi/*.yaml` is the source of truth for every
request/response shape any screen here needs to call.

**Deliberately excluded from the root npm workspace** (`package.json`'s
`"workspaces"` lists `apps/web-app` and `apps/shared-ui` explicitly, not
a wildcard) - Metro (this app's bundler) has known issues resolving
hoisted `node_modules` in an npm workspace, so this app manages its own
dependencies independently. `services/platform.js` and `services/auth.js`
are hand-ported copies of `apps/shared-ui`'s files (see each file's own
header comment) - if the original changes, re-sync by hand, there's no
build tooling sharing code between the two right now.

**Verified working (Metro bundle succeeds for both iOS and Android, 535+
modules resolve cleanly)** as of the initial scaffold - but this was
built without a real device/simulator available to run it on, and
without live access to check whether `atob()` exists in this exact
Hermes version (worked around entirely in `services/auth.js` rather than
assumed - see that file). Actually run this on a simulator or device
before assuming more than "it bundles."

**Local development:** copy `.env.example` to `.env` and use your
machine's real LAN IP, not `localhost` - see `services/platform.js`'s
comment for why.
