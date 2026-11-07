/**
 * App root: restore the session, then render either the auth screen or the
 * role's workspace (tab bar + stack).
 *
 * Client-side role routing is presentation only, never the security
 * boundary - that is enforced server-side by every service's require_role()
 * (ADR-0002). A tampered token gets a 403 from the API.
 */
import { useState } from "react";
import { ActivityIndicator, StatusBar, View } from "react-native";
import { colors } from "./theme";
import { DEMO_MODE } from "./services/platform";
import { installMockApi } from "./services/demo";
import { NavProvider, useNav } from "./lib/nav";
import { SessionProvider, useSession } from "./lib/session";
import { TabBar, TopBar } from "./components/AppShell";
import { Confirm } from "./components/ui";
import AuthScreen from "./screens/AuthScreen";
import { SCREENS, TABS_FOR_ROLE, TAB_FOR_ROUTE, homeFor } from "./screens";

// Patches global.fetch before any screen can call it. No-op unless demo
// mode is on; see services/platform.js's DEMO_MODE for when that is.
if (DEMO_MODE) installMockApi();

export default function App() {
  return (
    <SessionProvider>
      <StatusBar barStyle="dark-content" />
      <Root />
    </SessionProvider>
  );
}

function Root() {
  const { session, restoring } = useSession();

  if (restoring) {
    return (
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.ground }}>
        <ActivityIndicator color={colors.ink} />
      </View>
    );
  }

  if (!session) return <AuthScreen />;

  // Keying on the role tears the stack down on sign-out/sign-in, so the
  // next person never lands inside the previous one's screens.
  return (
    <NavProvider key={session.role} initial={homeFor(session.role)}>
      <Workspace />
    </NavProvider>
  );
}

function Workspace() {
  const { session, signOut } = useSession();
  const { route, reset } = useNav();
  const [confirmSignOut, setConfirmSignOut] = useState(false);

  const tabs = TABS_FOR_ROLE[session.role] || TABS_FOR_ROLE.customer;
  const entry = SCREENS[route.name] || SCREENS[homeFor(session.role)];
  const Screen = entry.component;
  const activeTab = TAB_FOR_ROUTE[route.name] || route.name;

  return (
    <View style={{ flex: 1, backgroundColor: colors.ground }}>
      <TopBar title={entry.title} onSignOut={() => setConfirmSignOut(true)} />
      <View style={{ flex: 1 }}>
        <Screen params={route.params} />
      </View>
      <TabBar tabs={tabs} current={activeTab} onSelect={(tab) => reset(tab.route)} />
      <Confirm
        visible={confirmSignOut}
        title="Sign out?"
        body="You'll need your email and password to get back in."
        confirmLabel="Sign out"
        onConfirm={() => { setConfirmSignOut(false); signOut(); }}
        onClose={() => setConfirmSignOut(false)}
      />
    </View>
  );
}
