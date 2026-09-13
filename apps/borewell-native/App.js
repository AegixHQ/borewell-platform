import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Button,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { Picker } from "@react-native-picker/picker";
import * as SecureStore from "expo-secure-store";
import { login, registerAccount, decodeJwtPayload } from "./services/auth";
import { PLATFORM_SPINE_URL } from "./services/platform";
import CustomerDashboard from "./screens/CustomerDashboard";
import ContractorDashboard from "./screens/ContractorDashboard";
import ResourceOwnerDashboard from "./screens/ResourceOwnerDashboard";

// Picker is imported from @react-native-picker/picker, not react-native
// core - confirmed by checking this exact installed react-native version
// (0.87.1) before writing this file: plain Picker has been removed from
// core (only ImagePickerIOS/DatePickerIOS remain, both explicitly
// deprecated stubs). @react-native-picker/picker@2.11.4 installed
// alongside this file - not a guess left for later.

const SESSION_STORAGE_KEY = "borewell_session";

const ROLES = [
  { value: "customer", label: "Customer" },
  { value: "contractor", label: "Contractor" },
  { value: "resource_owner", label: "Resource Owner" },
];

const DASHBOARDS = {
  customer: CustomerDashboard,
  contractor: ContractorDashboard,
  resource_owner: ResourceOwnerDashboard,
  admin: ContractorDashboard, // matches web-app: no dedicated admin UI yet
};

export default function App() {
  const [session, setSession] = useState(null);
  const [checkingSession, setCheckingSession] = useState(true);

  const [mode, setMode] = useState("login");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");

  const [regEmail, setRegEmail] = useState("");
  const [regPassword, setRegPassword] = useState("");
  const [regPhone, setRegPhone] = useState("");
  const [regRole, setRegRole] = useState("customer");

  // On cold start, check for a persisted session - this is the one thing
  // genuinely different from web-app's App.jsx (a browser tab losing its
  // in-memory session on reload is an accepted web tradeoff; a native
  // app forcing a re-login every time it's reopened would be a real, bad
  // experience). Uses expo-secure-store (Keychain on iOS, Keystore on
  // Android) rather than AsyncStorage specifically because this is
  // storing an auth token, not arbitrary app data.
  useEffect(() => {
    (async () => {
      try {
        const stored = await SecureStore.getItemAsync(SESSION_STORAGE_KEY);
        if (stored) {
          setSession(JSON.parse(stored));
        }
      } catch (err) {
        // A corrupted/unreadable stored session should fall back to the
        // login screen, not crash the app on every cold start.
        void err;
      } finally {
        setCheckingSession(false);
      }
    })();
  }, []);

  async function persistSession(newSession) {
    setSession(newSession);
    try {
      await SecureStore.setItemAsync(SESSION_STORAGE_KEY, JSON.stringify(newSession));
    } catch (err) {
      // Login/register still succeeds even if persistence fails (e.g. no
      // Keychain access on this device) - the user just has to log in
      // again next cold start, which is a degraded experience, not a
      // broken one.
      void err;
    }
  }

  async function handleLogout() {
    setSession(null);
    try {
      await SecureStore.deleteItemAsync(SESSION_STORAGE_KEY);
    } catch (err) {
      void err;
    }
  }

  async function handleLogin() {
    setError(null);
    setBusy(true);
    try {
      const { access_token: accessToken } = await login(
        PLATFORM_SPINE_URL,
        loginEmail,
        loginPassword
      );
      const payload = decodeJwtPayload(accessToken);
      await persistSession({ token: accessToken, role: payload.role, email: loginEmail });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleRegister() {
    setError(null);
    setBusy(true);
    try {
      const { access_token: accessToken } = await registerAccount(PLATFORM_SPINE_URL, {
        email: regEmail,
        password: regPassword,
        phone: regPhone,
        role: regRole,
      });
      const payload = decodeJwtPayload(accessToken);
      await persistSession({ token: accessToken, role: payload.role, email: regEmail });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  if (checkingSession) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" />
      </View>
    );
  }

  if (session) {
    // Client-side routing for UX/presentation ONLY - not the security
    // boundary, same as web-app. The real boundary is every backend
    // service's require_role dependency.
    const Dashboard = DASHBOARDS[session.role] || CustomerDashboard;
    return (
      <View style={{ flex: 1 }}>
        <Dashboard session={session} />
        <View style={styles.logoutBar}>
          <Button title="Log Out" onPress={handleLogout} />
        </View>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Borewell Platform</Text>

      <View style={styles.tabs}>
        <Button title="Log In" onPress={() => setMode("login")} disabled={mode === "login"} />
        <Button
          title="Register"
          onPress={() => setMode("register")}
          disabled={mode === "register"}
        />
      </View>

      {mode === "login" && (
        <View>
          <Text style={styles.label}>Email</Text>
          <TextInput
            style={styles.input}
            value={loginEmail}
            onChangeText={setLoginEmail}
            autoCapitalize="none"
            keyboardType="email-address"
          />
          <Text style={styles.label}>Password</Text>
          <TextInput
            style={styles.input}
            value={loginPassword}
            onChangeText={setLoginPassword}
            secureTextEntry
          />
          <Button title={busy ? "Logging in..." : "Log In"} onPress={handleLogin} disabled={busy} />
        </View>
      )}

      {mode === "register" && (
        <View>
          <Text style={styles.label}>Email</Text>
          <TextInput
            style={styles.input}
            value={regEmail}
            onChangeText={setRegEmail}
            autoCapitalize="none"
            keyboardType="email-address"
          />
          <Text style={styles.label}>Password (min 8 characters)</Text>
          <TextInput
            style={styles.input}
            value={regPassword}
            onChangeText={setRegPassword}
            secureTextEntry
          />
          <Text style={styles.label}>Phone (optional)</Text>
          <TextInput
            style={styles.input}
            value={regPhone}
            onChangeText={setRegPhone}
            keyboardType="phone-pad"
          />
          <Text style={styles.label}>I am a...</Text>
          <Picker selectedValue={regRole} onValueChange={setRegRole} style={styles.input}>
            {ROLES.map((r) => (
              <Picker.Item key={r.value} label={r.label} value={r.value} />
            ))}
          </Picker>
          <Button
            title={busy ? "Registering..." : "Register"}
            onPress={handleRegister}
            disabled={busy}
          />
        </View>
      )}

      {error && <Text style={styles.error}>{error}</Text>}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 20, paddingTop: 60 },
  centered: { flex: 1, justifyContent: "center", alignItems: "center" },
  title: { fontSize: 24, fontWeight: "600", marginBottom: 16 },
  tabs: { flexDirection: "row", gap: 12, marginBottom: 16 },
  label: { fontSize: 13, color: "#555", marginTop: 12, marginBottom: 4 },
  input: {
    borderWidth: 1,
    borderColor: "#ccc",
    borderRadius: 6,
    padding: 10,
    fontSize: 16,
  },
  error: {
    color: "#b00020",
    borderWidth: 1,
    borderColor: "#b00020",
    borderRadius: 6,
    padding: 8,
    marginTop: 16,
  },
  logoutBar: {
    padding: 12,
    borderTopWidth: 1,
    borderTopColor: "#eee",
  },
});
