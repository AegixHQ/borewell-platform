/**
 * Data-loading helpers - the native counterpart of
 * apps/web-app/src/lib/hooks.js. Deliberately not React Query:
 * Architecture doc section 3 calls for component state + fetch until there
 * is a real cross-screen caching problem.
 *
 * One addition over the web version: polling stops while the app is in the
 * background and runs once immediately on return. A phone app left open in
 * a pocket would otherwise poll four services all day for nothing.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { AppState } from "react-native";
import { RESOURCE_NETWORK_URL, lookupServiceArea } from "../services/platform";
import { useSession } from "./session";

export function useLoad(loader, deps = [], { pollMs } = {}) {
  const [state, setState] = useState({ data: undefined, error: null, loading: true });
  const mounted = useRef(true);
  const loaderRef = useRef(loader);
  loaderRef.current = loader;

  const run = useCallback(async ({ quiet = false } = {}) => {
    if (!quiet) setState((s) => ({ ...s, loading: true }));
    try {
      const data = await loaderRef.current();
      if (mounted.current) setState({ data, error: null, loading: false });
      return data;
    } catch (err) {
      if (mounted.current) setState((s) => ({ data: s.data, error: err, loading: false }));
      return undefined;
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    run();
    return () => { mounted.current = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    if (!pollMs) return undefined;
    // There are no websockets or push notifications in the backend yet (see
    // docs/adr/0005-field-console-ui.md's API gaps) - screens that need to
    // see a change made by someone else poll on a slow interval.
    let id = setInterval(() => run({ quiet: true }), pollMs);
    const sub = AppState.addEventListener("change", (next) => {
      clearInterval(id);
      if (next === "active") {
        run({ quiet: true });
        id = setInterval(() => run({ quiet: true }), pollMs);
      }
    });
    return () => { clearInterval(id); sub.remove(); };
  }, [pollMs, run]);

  return { ...state, reload: run };
}

/** Tracks a one-off action (save, approve, accept) with busy + error state. */
export function useAction() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const run = useCallback(async (fn, { onError } = {}) => {
    setBusy(true);
    setError(null);
    try {
      return await fn();
    } catch (err) {
      setError(onError ? onError(err) : err.message);
      return undefined;
    } finally {
      setBusy(false);
    }
  }, []);
  return { busy, error, setError, run };
}

/** Transient confirmation message ("Saved", "Request sent"). */
export function useToast(ms = 2600) {
  const [message, setMessage] = useState(null);
  useEffect(() => {
    if (!message) return undefined;
    const id = setTimeout(() => setMessage(null), ms);
    return () => clearTimeout(id);
  }, [message, ms]);
  return [message, setMessage];
}

// Service-area lookups are pure reference data and get hit once per job
// card, so cache them for the app's lifetime. Key is rounded to ~100 m,
// which is well inside any pilot area's radius.
const areaCache = new Map();

/**
 * Village/area name for a job location. Jobs only carry lat/lng - there is
 * no address field on the API - so the pilot service area is the closest
 * thing to a human-readable place name.
 */
export function useAreaName(lat, lng) {
  const { session } = useSession();
  const key = lat === undefined || lat === null ? null : keyFor(lat, lng);
  // The cache is the state; this only forces a re-render once a lookup
  // lands, so a cache hit costs nothing and needs no state write.
  const [, bump] = useState(0);

  useEffect(() => {
    if (!key || !session || areaCache.has(key)) return undefined;
    let cancelled = false;
    const done = (value) => {
      areaCache.set(key, value);
      if (!cancelled) bump((n) => n + 1);
    };
    lookupServiceArea(RESOURCE_NETWORK_URL, session.token, { lat, lng })
      .then(done)
      // 404 is the expected answer outside the pilot villages, not an error.
      .catch(() => done(null));
    return () => { cancelled = true; };
  }, [key, lat, lng, session]);

  return key ? areaCache.get(key) : undefined;
}

function keyFor(lat, lng) {
  return `${Number(lat).toFixed(3)},${Number(lng).toFixed(3)}`;
}

export function clearAreaCache() {
  areaCache.clear();
}
