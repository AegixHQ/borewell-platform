/**
 * Everyone on the platform, and the one thing only an admin can do here: add a
 * contractor. The admin picks the password (or generates one) and hands it over
 * out of band - the server never returns it, so after a successful add this
 * screen shows the credentials once, in the sheet, and nowhere else.
 */
import { useMemo, useState } from "react";
import { View } from "react-native";
import { PLATFORM_SPINE_URL, createContractor, listUsers } from "../../services/platform";
import { formatRelative } from "../../theme";
import { assertValid, chain, emailError, generatePassword, normaliseEmail, passwordError, phoneError, useFieldRefs } from "../../lib/form";
import { useAction, useLoad, useToast } from "../../lib/hooks";
import { useSession } from "../../lib/session";
import { PageHeader } from "../../components/AppShell";
import {
  Alert, Avatar, Badge, Body, Button, Card, EmptyState, Field, Input, Inset, KeyValue, Loading, Pills, Row, Screen, Sheet, Toast,
} from "../../components/ui";

const ROLE_FILTERS = [
  { value: "all", label: "All" },
  { value: "customer", label: "Customers" },
  { value: "contractor", label: "Contractors" },
  { value: "resource_owner", label: "Rig owners" },
  { value: "admin", label: "Admins" },
];
const ROLE_LABELS = { customer: "Customer", contractor: "Contractor", resource_owner: "Rig owner", admin: "Admin" };
const ROLE_TONES = { customer: "neutral", contractor: "saffron", resource_owner: "slate", admin: "green" };

export default function AdminPeople() {
  const { session } = useSession();
  const [filter, setFilter] = useState("all");
  const [adding, setAdding] = useState(false);
  const [toast, setToast] = useToast();

  const users = useLoad(() => listUsers(PLATFORM_SPINE_URL, session.token), [session.token]);

  const counts = useMemo(() => {
    const out = { all: (users.data || []).length };
    (users.data || []).forEach((u) => { out[u.role] = (out[u.role] || 0) + 1; });
    return out;
  }, [users.data]);
  const shown = (users.data || []).filter((u) => filter === "all" || u.role === filter);

  return (
    <Screen>
      <PageHeader title="People" subtitle="Every account on the platform" />

      <Button title="Add contractor" variant="saffron" trailing onPress={() => setAdding(true)} />

      <Pills
        value={filter}
        onChange={setFilter}
        options={ROLE_FILTERS.map((f) => ({ ...f, count: counts[f.value] ?? 0 }))}
      />

      {!!users.error && <Alert>{users.error.message}</Alert>}
      {users.loading && !users.data && <Card><Loading label="Loading accounts…" /></Card>}
      {users.data && shown.length === 0 && (
        <Card><EmptyState title="No accounts here">Nobody has this role yet.</EmptyState></Card>
      )}

      {shown.map((user) => (
        <Card key={user.user_id}>
          <Row gap={12}>
            <Avatar initials={(user.email || "?").slice(0, 2).toUpperCase()} />
            <View style={{ flex: 1, gap: 2 }}>
              <Body size={15} weight="700" numberOfLines={1}>{user.email}</Body>
              <Body size={12} muted>
                {user.phone ? `${user.phone} · ` : ""}joined {user.created_at ? formatRelative(user.created_at) : "—"}
              </Body>
            </View>
            <Badge tone={ROLE_TONES[user.role] || "neutral"}>{ROLE_LABELS[user.role] || user.role}</Badge>
          </Row>
        </Card>
      ))}

      {adding && (
        <AddContractorSheet
          token={session.token}
          onClose={() => setAdding(false)}
          onAdded={async () => { setToast("Contractor added"); await users.reload(); }}
        />
      )}
      <Toast message={toast} />
    </Screen>
  );
}

function AddContractorSheet({ token, onClose, onAdded }) {
  const action = useAction();
  const refs = useFieldRefs(3); // email, phone, password
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [created, setCreated] = useState(null); // credentials, shown once after success

  async function submit() {
    await action.run(async () => {
      assertValid({
        email: emailError(email),
        phone: phoneError(phone),
        password: passwordError(password),
      });
      const cleanEmail = normaliseEmail(email);
      await createContractor(PLATFORM_SPINE_URL, token, { email: cleanEmail, password, phone: phone.trim() });
      setCreated({ email: cleanEmail, password });
      await onAdded();
    });
  }

  if (created) {
    return (
      <Sheet visible title="Contractor added" onClose={onClose} actions={<Button title="Done" onPress={onClose} />}>
        <Alert tone="ok">Share these sign-in details with them now - the password is not shown again.</Alert>
        <Inset>
          <KeyValue k="Email" v={created.email} />
          <KeyValue k="Password" v={created.password} />
        </Inset>
        <Body size={13} muted>They sign in with these on the normal sign-in screen and land on the contractor workspace.</Body>
      </Sheet>
    );
  }

  return (
    <Sheet
      visible
      title="Add contractor"
      onClose={onClose}
      actions={
        <Row gap={10}>
          <Button title="Cancel" variant="light" style={{ flex: 1 }} onPress={onClose} />
          <Button title={action.busy ? "Adding…" : "Add contractor"} style={{ flex: 1.4 }} busy={action.busy} onPress={submit} />
        </Row>
      }
    >
      <Field label="Email" error={action.fieldErrors.email}>
        <Input
          value={email}
          onChangeText={(v) => { setEmail(v); action.clearFieldError("email"); }}
          placeholder="contractor@example.com"
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="email-address"
          {...chain(refs, 0, submit)}
        />
      </Field>
      <Field label="Phone" hint="Optional" error={action.fieldErrors.phone}>
        <Input
          value={phone}
          onChangeText={(v) => { setPhone(v); action.clearFieldError("phone"); }}
          placeholder="98765 43210"
          keyboardType="phone-pad"
          {...chain(refs, 1, submit)}
        />
      </Field>
      <Field label="Password" hint="At least 8 characters. You hand this over; it is not emailed." error={action.fieldErrors.password}>
        <Input
          value={password}
          onChangeText={(v) => { setPassword(v); action.clearFieldError("password"); }}
          placeholder="Choose or generate one"
          autoCapitalize="none"
          autoCorrect={false}
          {...chain(refs, 2, submit)}
        />
      </Field>
      <Button
        title="Generate a password"
        variant="light"
        size="sm"
        onPress={() => { setPassword(generatePassword()); action.clearFieldError("password"); }}
      />
      {!!action.error && <Alert>{action.error}</Alert>}
    </Sheet>
  );
}

