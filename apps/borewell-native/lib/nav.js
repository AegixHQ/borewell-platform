/**
 * A ~90 line stack navigator.
 *
 * react-navigation is the obvious choice and would be the right one for a
 * bigger app, but it pulls in react-native-screens and
 * react-native-safe-area-context - two native modules whose versions have
 * to line up with the Expo SDK, and the registry was unreachable when this
 * was built (see components/ui.js's Icon comment for the same call).
 * Nothing here needs deep links, gestures or nested navigators: it is one
 * stack per role with a tab bar on top of it.
 *
 * If this app grows, replacing this with react-navigation is a contained
 * change: screens only use navigate/goBack/replace and a params object.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { BackHandler } from "react-native";

const NavContext = createContext(null);

export function NavProvider({ initial, children }) {
  const [stack, setStack] = useState([{ name: initial, params: {} }]);

  const navigate = useCallback((name, params = {}) => {
    setStack((s) => [...s, { name, params }]);
  }, []);

  const replace = useCallback((name, params = {}) => {
    setStack((s) => [...s.slice(0, -1), { name, params }]);
  }, []);

  /** Tab switch: one entry, so Back never walks through old tabs. */
  const reset = useCallback((name, params = {}) => {
    setStack([{ name, params }]);
  }, []);

  const goBack = useCallback(() => {
    let popped = false;
    setStack((s) => {
      if (s.length <= 1) return s;
      popped = true;
      return s.slice(0, -1);
    });
    return popped;
  }, []);

  // Android hardware back. Returning false at the root lets the OS close
  // the app, which is what people expect there.
  useEffect(() => {
    const sub = BackHandler.addEventListener("hardwareBackPress", () => {
      if (stack.length <= 1) return false;
      setStack((s) => s.slice(0, -1));
      return true;
    });
    return () => sub.remove();
  }, [stack.length]);

  const route = stack[stack.length - 1];
  const value = useMemo(
    () => ({ route, depth: stack.length, navigate, replace, reset, goBack }),
    [route, stack.length, navigate, replace, reset, goBack]
  );

  return <NavContext.Provider value={value}>{children}</NavContext.Provider>;
}

export function useNav() {
  const ctx = useContext(NavContext);
  if (!ctx) throw new Error("useNav must be used inside <NavProvider>");
  return ctx;
}
