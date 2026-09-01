/**
 * Auth helpers shared across all 3 apps. Two things live here, and only
 * two - see AGENTS.md's rule against unnecessary abstraction:
 *
 * 1. decodeJwtPayload - reads the role claim out of a JWT for UI routing
 *    ONLY. This does NOT verify the signature and must never be treated as
 *    an authorization check - that boundary is enforced server-side by
 *    each service's require_role dependency (see each service's
 *    app/deps.py) and proven by that service's isolation tests, not by
 *    anything here.
 *
 * 2. login - calls platform-spine's real /v1/auth/login endpoint. The only
 *    service that issues tokens (RFC 0001 section 5); every app logs in
 *    through the same call, which is the actual "unified auth" - not a
 *    single unified frontend, three separate ones sharing one auth call.
 */

export function decodeJwtPayload(token) {
  const payloadSegment = token.split(".")[1];
  const base64 = payloadSegment.replace(/-/g, "+").replace(/_/g, "/");
  const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), "=");
  const json = atob(padded);
  return JSON.parse(json);
}

export async function login(platformSpineUrl, email, password) {
  const response = await fetch(`${platformSpineUrl}/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body?.error?.message || "Login failed");
  }
  return response.json(); // { access_token, role }
}
