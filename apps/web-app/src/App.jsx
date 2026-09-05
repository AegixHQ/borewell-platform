import { useState } from "react";
import { login, registerAccount, decodeJwtPayload } from "shared-ui";
import CustomerDashboard from "./dashboards/CustomerDashboard.jsx";
import ContractorDashboard from "./dashboards/ContractorDashboard.jsx";
import ResourceOwnerDashboard from "./dashboards/ResourceOwnerDashboard.jsx";

const PLATFORM_SPINE_URL =
  import.meta.env.VITE_PLATFORM_SPINE_URL || "http://localhost:8001";

const ROLES = [
  { value: "customer", label: "Customer" },
  { value: "contractor", label: "Contractor" },
  { value: "resource_owner", label: "Resource Owner" },
];

const DASHBOARDS = {
  customer: CustomerDashboard,
  contractor: ContractorDashboard,
  resource_owner: ResourceOwnerDashboard,
  admin: ContractorDashboard, // admin sees the contractor view for now - no dedicated admin UI yet
};

export default function App() {
  const [mode, setMode] = useState("login"); // "login" | "register"
  const [session, setSession] = useState(null); // { token, role, email }
  const [error, setError] = useState(null);

  // Login form state
  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");

  // Register form state - role is chosen HERE, and only here.
  const [regEmail, setRegEmail] = useState("");
  const [regPassword, setRegPassword] = useState("");
  const [regPhone, setRegPhone] = useState("");
  const [regRole, setRegRole] = useState("customer");

  async function handleLogin(event) {
    event.preventDefault();
    setError(null);
    try {
      // Role is NOT entered here - it comes back from the backend
      // automatically, decoded from the real JWT platform-spine issues.
      const { access_token: accessToken, role } = await login(
        PLATFORM_SPINE_URL,
        loginEmail,
        loginPassword
      );
      const payload = decodeJwtPayload(accessToken);
      setSession({ token: accessToken, role: payload.role, email: loginEmail });
      void role; // response role and JWT-decoded role should always match; kept for clarity
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleRegister(event) {
    event.preventDefault();
    setError(null);
    try {
      const { access_token: accessToken, role } = await registerAccount(
        PLATFORM_SPINE_URL,
        { email: regEmail, password: regPassword, phone: regPhone, role: regRole }
      );
      const payload = decodeJwtPayload(accessToken);
      setSession({ token: accessToken, role: payload.role, email: regEmail });
      void role;
    } catch (err) {
      setError(err.message);
    }
  }

  if (session) {
    // Client-side routing for UX/presentation ONLY - not the security
    // boundary. The real boundary is every backend service's require_role
    // dependency, proven by each service's isolation tests (see e.g.
    // resource-network's test_resource_owner_cannot_create_resource_yet).
    const Dashboard = DASHBOARDS[session.role] || CustomerDashboard;
    return <Dashboard session={session} />;
  }

  return (
    <div>
      <h1>Borewell Platform</h1>

      <nav>
        <button onClick={() => setMode("login")} disabled={mode === "login"}>
          Log In
        </button>
        <button onClick={() => setMode("register")} disabled={mode === "register"}>
          Register
        </button>
      </nav>

      {mode === "login" && (
        <form onSubmit={handleLogin}>
          <h2>Log In</h2>
          <label>
            Email
            <input
              type="email"
              value={loginEmail}
              onChange={(e) => setLoginEmail(e.target.value)}
              required
            />
          </label>
          <label>
            Password
            <input
              type="password"
              value={loginPassword}
              onChange={(e) => setLoginPassword(e.target.value)}
              required
            />
          </label>
          <button type="submit">Log In</button>
        </form>
      )}

      {mode === "register" && (
        <form onSubmit={handleRegister}>
          <h2>Register</h2>
          <label>
            Email
            <input
              type="email"
              value={regEmail}
              onChange={(e) => setRegEmail(e.target.value)}
              required
            />
          </label>
          <label>
            Password
            <input
              type="password"
              value={regPassword}
              onChange={(e) => setRegPassword(e.target.value)}
              minLength={8}
              required
            />
          </label>
          <label>
            Phone (optional)
            <input
              type="tel"
              value={regPhone}
              onChange={(e) => setRegPhone(e.target.value)}
            />
          </label>
          <label>
            I am a...
            <select value={regRole} onChange={(e) => setRegRole(e.target.value)}>
              {ROLES.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </select>
          </label>
          <button type="submit">Register</button>
        </form>
      )}

      {error && <p role="alert">{error}</p>}
    </div>
  );
}
