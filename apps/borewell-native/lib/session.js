/**
 * Session state for the whole app - the native counterpart of
 * apps/web-app/src/lib/session.jsx.
 *
 * The role kept here drives WHICH SCREENS RENDER - presentation only. It is
 * never an authorization check: every service enforces access server-side
 * with require_role() (see each service's app/deps.py and its isolation
 * tests). A tampered token gets a 403 from the API, which is the boundary
 * that matters.
 *
 * Difference from the web app: the token is persisted. A browser tab losing
 * its session on reload is an accepted web tradeoff; a phone app asking for
 * a password every time it is reopened is not. expo-secure-store (Keychain
 * on iOS, Keystore on Android) is used rather than AsyncStorage precisely
 * because this is an auth token, not arbitrary app data.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import * as SecureStore from "expo-secure-store";
import { decodeJwtPayload } from "../services/auth";

const STORAGE_KEY = "borewell_session";
const SessionContext = createContext(null);

export function SessionProvider({ children }) {
  const [session, setSession] = useState(null);
  const [restoring, setRestoring] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const raw = await SecureStore.getItemAsync(STORAGE_KEY);
        if (raw) {
          const saved = JSON.parse(raw);
          const payload = decodeJwtPayload(saved.token);
          // exp is seconds since epoch; drop an expired token rather than
          // letting every call fail with a 401 the user can't explain.
          if (saved?.token && (!payload?.exp || payload.exp * 1000 > Date.now())) {
            setSession({ ...saved, role: payload.role || saved.role });
          }
        }
      } catch {
        // A corrupted or unreadable stored session falls back to sign-in
        // rather than crashing on every cold start.
      } finally {
        setRestoring(false);
      }
    })();
  }, []);

  const signIn = useCallback(async ({ token, email }) => {
    const payload = decodeJwtPayload(token);
    const next = { token, email, role: payload.role, userId: payload.sub };
    setSession(next);
    try {
      await SecureStore.setItemAsync(STORAGE_KEY, JSON.stringify(next));
    } catch {
      // Signing in still works if the keychain is unavailable - the user
      // just has to sign in again next cold start.
    }
  }, []);

  const signOut = useCallback(async () => {
    setSession(null);
    try {
      await SecureStore.deleteItemAsync(STORAGE_KEY);
    } catch {
      // Nothing useful to do; the in-memory session is already gone.
    }
  }, []);

  const value = useMemo(
    () => ({ session, restoring, signIn, signOut }),
    [session, restoring, signIn, signOut]
  );
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used inside <SessionProvider>");
  return ctx;
}
