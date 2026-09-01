import { useState } from "react";
import { login, decodeJwtPayload } from "shared-ui";

const EXPECTED_ROLE = "resource_owner";
const PLATFORM_SPINE_URL =
  import.meta.env.VITE_PLATFORM_SPINE_URL || "http://localhost:8001";

export default function App() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [session, setSession] = useState(null); // { token, role }

  async function handleSubmit(event) {
    event.preventDefault();
    setError(null);
    try {
      const { access_token: accessToken, role } = await login(
        PLATFORM_SPINE_URL,
        email,
        password
      );

      // Client-side check for routing/UX only - NOT the security boundary.
      // The real boundary is every backend service rejecting this role
      // from endpoints it isn't allowed to call, proven in each service's
      // test suite (e.g. resource-network's
      // test_resource_owner_cannot_create_resource_yet).
      const payload = decodeJwtPayload(accessToken);
      if (role !== EXPECTED_ROLE || payload.role !== EXPECTED_ROLE) {
        setError(
          `This app is for resource owners. Your account role is "${role}" - ` +
            "log in through the app for that role instead."
        );
        return;
      }
      setSession({ token: accessToken, role });
    } catch (err) {
      setError(err.message);
    }
  }

  if (session) {
    return (
      <div>
        <h1>Resource Owner Dashboard</h1>
        <p>
          Signed in with role: <strong>{session.role}</strong>
        </p>
        <p>
          Rig/equipment management and job-request views are Phase 1 (RFC
          0001 section 7) - not built yet. resource-network's data model
          currently keys resources to the contractor, not to an independent
          resource owner, so there is nothing real to show here until that
          changes. This screen exists to prove role-based auth and routing
          work end to end, not to be the finished dashboard.
        </p>
      </div>
    );
  }

  return (
    <div>
      <h1>Resource Owner App</h1>
      <form onSubmit={handleSubmit}>
        <label>
          Email
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>
        <button type="submit">Log in</button>
        {error && <p role="alert">{error}</p>}
      </form>
    </div>
  );
}
