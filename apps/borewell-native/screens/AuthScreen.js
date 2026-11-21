/**
 * Sign in / create account - the one screen shown before a session exists.
 *
 * Role is chosen ONCE, here, at registration, and never asked for again:
 * login returns it and it is decoded from the JWT (ADR-0002). Don't add a
 * role picker to the sign-in side.
 */
import { useState } from "react";
import { KeyboardAvoidingView, Platform, ScrollView, Text, View } from "react-native";
import { googleLogin, login, registerAccount } from "../services/auth";
import { DEMO_MODE, PLATFORM_SPINE_URL } from "../services/platform";
import { DEMO_ACCOUNTS } from "../services/demo";
import { colors } from "../theme";
import { useAction } from "../lib/hooks";
import {
  assertValid, chain, emailError, normaliseEmail, passwordError, phoneError, useFieldRefs,
} from "../lib/form";
import { useSession } from "../lib/session";
import { GOOGLE_ENABLED, getGoogleIdToken } from "../lib/google";
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
  const { busy, error, fieldErrors, clearFieldError, run } = useAction();
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [phone, setPhone] = useState("");
  const [role, setRole] = useState("customer");
  const [notice, setNotice] = useState(null);

  const registering = mode === "register";
  const refs = useFieldRefs(3); // email, phone, password
  const order = registering ? refs : [refs[0], refs[2]]; // sign-in has no phone field

  async function submit() {
    await run(async () => {
      const cleanEmail = normaliseEmail(email);
      assertValid({
        email: emailError(email),
        phone: registering ? phoneError(phone) : null,
        password: registering ? passwordError(password) : password ? null : "Enter your password.",
      });
      const { access_token: token } = registering
        ? await registerAccount(PLATFORM_SPINE_URL, { email: cleanEmail, password, phone, role })
        : await login(PLATFORM_SPINE_URL, cleanEmail, password);
      await signIn({ token, email: cleanEmail });
    });
  }

  async function continueWithGoogle() {
    setNotice(null);
    await run(async () => {
      const google = await getGoogleIdToken();
      if (!google) return; // closed the Google picker - nothing to report
      try {
        const { access_token: token } = await googleLogin(
          PLATFORM_SPINE_URL, google.idToken, registering ? role : undefined
        );
        await signIn({ token, email: google.email });
      } catch (err) {
        if (err.code !== "ROLE_REQUIRED") throw err;
        // First time with this Google account: role is chosen once, here.
        setMode("register");
        setNotice("New here? Choose how you're joining, then tap Continue with Google again.");
      }
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
            <Field label="I am joining as" error={fieldErrors.role}>
              <Pills
                value={role}
                onChange={(value) => {
                  setRole(value);
                  clearFieldError("role");
                }}
                options={ROLE_OPTIONS}
              />
            </Field>
          )}

          <Field label="Email" error={fieldErrors.email}>
            <Input
              value={email}
              onChangeText={(value) => { setEmail(value); clearFieldError("email"); }}
              placeholder="you@example.com"
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="email-address"
              textContentType="emailAddress"
              autoComplete="email"
              {...chain(order, 0, submit)}
            />
          </Field>

          {registering && (
            <Field label="Phone" hint="Optional" error={fieldErrors.phone}>
              <Input
                value={phone}
                onChangeText={(value) => { setPhone(value); clearFieldError("phone"); }}
                placeholder="+91 "
                keyboardType="phone-pad"
<<<<<<< HEAD
=======
                {...chain(order, 1, submit)}
>>>>>>> origin/main
              />
            </Field>
          )}

          <Field label="Password" hint={registering ? "At least 8 characters" : undefined} error={fieldErrors.password}>
            <Input
              value={password}
              onChangeText={(value) => { setPassword(value); clearFieldError("password"); }}
              placeholder="••••••••"
              secureTextEntry
              autoCapitalize="none"
              textContentType={registering ? "newPassword" : "password"}
              {...chain(order, order.length - 1, submit)}
            />
          </Field>

          {!!error && <Alert>{error}</Alert>}
          {!!notice && <Alert tone="info">{notice}</Alert>}

          <Button
            title={busy ? (registering ? "Creating…" : "Signing in…") : registering ? "Create account" : "Sign in"}
            size="lg"
            trailing
            busy={busy}
            onPress={submit}
          />

          {GOOGLE_ENABLED && !DEMO_MODE && (
            <Button
              title="Continue with Google"
              variant="light"
              size="lg"
              busy={busy}
              onPress={continueWithGoogle}
            />
          )}

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
