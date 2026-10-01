/**
 * Who you are signed in as, what this build is talking to, and the way out.
 * The web app puts sign-out in the top nav; on a phone it needs a home.
 */
import { View } from "react-native";
import {
  DEMO_MODE, PAYMENTS_URL, PLATFORM_SPINE_URL, QUOTATION_URL, RESOURCE_NETWORK_URL,
} from "../services/platform";
import { colors } from "../theme";
import { useSession } from "../lib/session";
import { PageHeader } from "../components/AppShell";
import {
  Alert, Avatar, Body, Button, Card, Inset, Row, Screen, Title,
} from "../components/ui";

const ROLE_LABELS = {
  customer: "Customer",
  contractor: "Contractor",
  resource_owner: "Rig owner",
  admin: "Admin",
};

export default function Account() {
  const { session, signOut } = useSession();
  const initials = (session.email || "?").slice(0, 2).toUpperCase();

  return (
    <Screen>
      <PageHeader title="Account" />

      <Card>
        <Row gap={14}>
          <Avatar initials={initials} size={54} />
          <View style={{ flex: 1, gap: 2 }}>
            <Title size={19}>{ROLE_LABELS[session.role] || session.role}</Title>
            <Body size={13} muted>{session.email}</Body>
          </View>
        </Row>
        <Body size={13} muted>
          Your role is set once, when the account is created, and decides which workspace you see. It can’t be
          changed by signing in again.
        </Body>
      </Card>

      {DEMO_MODE ? (
        <Card>
          <Title size={19}>Demo mode</Title>
          <Alert tone="info">
            This build is running against an in-memory stand-in for the backend. Everything works, nothing is
            saved, and it all resets when the app reloads.
          </Alert>
          <Body size={13} muted>
            To point it at the real services, copy .env.example to .env, put your machine’s LAN IP in it and
            restart Expo.
          </Body>
        </Card>
      ) : (
        <Card>
          <Title size={19}>Connected to</Title>
          <Inset>
            <Body size={12} muted>Platform spine</Body>
            <Body size={13}>{PLATFORM_SPINE_URL}</Body>
            <Body size={12} muted>Quotation</Body>
            <Body size={13}>{QUOTATION_URL}</Body>
            <Body size={12} muted>Resource network</Body>
            <Body size={13}>{RESOURCE_NETWORK_URL}</Body>
            <Body size={12} muted>Payments</Body>
            <Body size={13}>{PAYMENTS_URL}</Body>
          </Inset>
        </Card>
      )}

      <Button title="Sign out" variant="light" onPress={signOut} />
      <Body size={12} muted style={{ textAlign: "center", color: colors.muted }}>
        Borewell Platform · Madurai pilot
      </Body>
    </Screen>
  );
}
