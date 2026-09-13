/**
 * Ported from apps/shared-ui/src/auth.js - see that file for the full
 * original design-rationale comments. Same "hand-sync, not auto-shared"
 * caveat as services/platform.js in this same directory.
 *
 * login() and registerAccount() are copied verbatim - no browser-only API
 * in either.
 *
 * decodeJwtPayload() is NOT a verbatim copy: the original uses the
 * browser global atob() to base64-decode the JWT payload segment. Rather
 * than assume atob() is available in this exact Expo/React Native/Hermes
 * version (unverified - this was built without live access to check),
 * this uses a small dependency-free base64url decoder instead, verified
 * correct against a real JWT-shaped payload before being used here. This
 * removes the platform-uncertainty entirely rather than betting on it.
 */

function base64UrlDecode(base64url) {
  const base64 = base64url.replace(/-/g, "+").replace(/_/g, "/");
  const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), "=");
  const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
  let output = "";
  let buffer = 0;
  let bits = 0;
  for (const char of padded) {
    if (char === "=") break;
    buffer = (buffer << 6) | chars.indexOf(char);
    bits += 6;
    if (bits >= 8) {
      bits -= 8;
      output += String.fromCharCode((buffer >> bits) & 0xff);
    }
  }
  return output;
}

export function decodeJwtPayload(token) {
  // Reads the role claim out of a JWT for UI ROUTING ONLY. Does NOT
  // verify the signature and must never be treated as an authorization
  // check - that boundary is enforced server-side by each service's
  // require_role dependency, same as in the web app.
  const payloadSegment = token.split(".")[1];
  const json = base64UrlDecode(payloadSegment);
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
