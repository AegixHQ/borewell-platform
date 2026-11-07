/**
 * Sign in / create account - the one screen shown before a session exists.
 *
 * Role is chosen ONCE, here, at registration, and never asked for again:
 * login returns it and it is decoded from the JWT (ADR-0002). Don't add a
 * role picker to the sign-in side.
 */
import { useState } from "react";
import { KeyboardAvoidingView, Platform, ScrollView, Text, View } from "react-native";
import { login, registerAccount } from "../services/auth";
import { DEMO_MODE, PLATFORM_SPINE_URL } from "../services/platform";
import { DEMO_ACCOUNTS } from "../services/demo";
import { colors } from "../theme";
import { useAction } from "../lib/hooks";
import { useSession } from "../lib/session";
import DepthGauge from "../components/DepthGauge";
import { TOP_INSET } from "../components/AppShell";
import { Alert, Body, Button, Card, Field, Input, Logo, Pills, Row, Title } from "../components/ui";

const ROLE_OPTIONS = [
  { value: "customer", label: "Customer" },
  { value: "contractor", label: "Contractor" },
  { value: "resource_owner", label: "Rig owner" },
];

export default function AuthScreen() {
  const { signIn } = useSession();
  const { busy, error, run } = useAction();
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [phone, setPhone] = useState("");
  const [role, setRole] = useState("customer");

  const registering = mode === "register";

  async function submit() {
    await run(async () => {
      const { access_token: token } = registering
        ? await registerAccount(PLATFORM_SPINE_URL, { email, password, phone, role })
        : await login(PLATFORM_SPINE_URL, email, password);
      await signIn({ token, email });
    });
  }

  return (
    <KeyboardAvoidingView style={{ flex: 1, backgroundColor: colors.chrome }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
      <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={{ flexGrow: 1 }}>
        <View style={{ paddingTop: TOP_INSET, paddingHorizontal: 22, paddingBottom: 26, gap: 14 }}>
          <Row gap={10}>
            <Logo size={36} />
            <Text style={{ color: "#fff", fontSize: 20, fontWeight: "800", letterSpacing: -0.4 }}>borewell</Text>
          </Row>
          <Row gap={16} align="flex-start">
            <View style={{ flex: 1, gap: 8 }}>
              <Title dark size={31}>Know the depth{"\n"}before you dig.</Title>
              <Body muted dark>
                Location-based quotes, nearby rigs and live drilling updates for Madurai district.
              </Body>
            </View>
            <DepthGauge min={380} max={520} water={440} height={150} width={74} dark labels={false} />
          </Row>
        </View>

        <View
          style={{
            flex: 1,
            backgroundColor: colors.ground,
            borderTopLeftRadius: 30,
            borderTopRightRadius: 30,
            padding: 22,
            paddingBottom: 40,
            gap: 16,
          }}
        >
          <Pills
            value={mode}
            onChange={setMode}
            options={[{ value: "login", label: "Sign in" }, { value: "register", label: "Create account" }]}
          />

          {registering && (
            <Field label="I am joining as">
              <Pills value={role} onChange={setRole} options={ROLE_OPTIONS} />
            </Field>
          )}

          <Field label="Email">
            <Input
              value={email}
              onChangeText={setEmail}
              placeholder="you@example.com"
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="email-address"
              textContentType="emailAddress"
            />
          </Field>

          {registering && (
            <Field label="Phone" hint="Optional">
              <Input value={phone} onChangeText={setPhone} placeholder="+91 " keyboardType="phone-pad" />
            </Field>
          )}

          <Field label="Password" hint={registering ? "At least 8 characters" : undefined}>
            <Input
              value={password}
              onChangeText={setPassword}
              placeholder="••••••••"
              secureTextEntry
              autoCapitalize="none"
              textContentType={registering ? "newPassword" : "password"}
            />
          </Field>

          {!!error && <Alert>{error}</Alert>}

          <Button
            title={busy ? (registering ? "Creating…" : "Signing in…") : registering ? "Create account" : "Sign in"}
            size="lg"
            trailing
            busy={busy}
            onPress={submit}
          />

          {registering && (
            <Body size={13} muted>
              Your role decides which workspace you see. It can’t be changed at sign-in.
            </Body>
          )}

          {DEMO_MODE && !registering && (
            <Card style={{ gap: 10 }}>
              <Body size={13} weight="700">Demo mode — pick an account (any password)</Body>
              <Pills
                value={email}
                onChange={(value) => { setEmail(value); setPassword("demo1234"); }}
                options={DEMO_ACCOUNTS.map((a) => ({ value: a.email, label: a.label }))}
              />
              <Body size={12} muted>
                Nothing is saved: everything resets when the app reloads.
              </Body>
            </Card>
          )}
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}
