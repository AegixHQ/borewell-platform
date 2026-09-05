/**
 * Auth helpers shared across the app(s). Per ADR-0002 (single unified
 * app, replacing the earlier 3-separate-apps architecture): this module
 * now backs one register+login flow, but stays here rather than moving
 * into apps/web-app/src directly, in case a future app (e.g. an admin
 * console) ever needs the same calls again.
 *
 * Three things live here, and only three:
 *
 * 1. decodeJwtPayload - reads the role claim out of a JWT for UI routing
 *    ONLY. Does NOT verify the signature and must never be treated as an
 *    authorization check - that boundary is enforced server-side by each
 *    service's require_role dependency (see each service's app/deps.py)
 *    and proven by that service's isolation tests, not by anything here.
 *
 * 2. login - calls platform-spine's real /v1/auth/login. Role comes back
 *    in the response automatically; the caller never asks the user to
 *    re-enter it.
 *
 * 3. registerAccount - calls platform-spine's real /v1/auth/register.
 *    Role is supplied by the caller at registration time (the one place
 *    the user actually chooses it) and is never asked for again.
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

export async function registerAccount(platformSpineUrl, { email, password, phone, role }) {
  const response = await fetch(`${platformSpineUrl}/v1/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, phone: phone || undefined, role }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body?.error?.message || "Registration failed");
  }
  return response.json(); // { access_token, role }
}
