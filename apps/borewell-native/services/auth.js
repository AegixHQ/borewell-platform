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

import { requestJson } from "./http";

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
  return requestJson(platformSpineUrl, "/v1/auth/login", {
    method: "POST",
    body: { email, password },
    fallbackMessage: "Login failed. Please try again.",
  });
}

export async function registerAccount(platformSpineUrl, { email, password, phone, role }) {
  return requestJson(platformSpineUrl, "/v1/auth/register", {
    method: "POST",
    body: { email, password, phone: phone || undefined, role },
    fallbackMessage: "Registration failed. Please try again.",
  });
}

// Google sign-in: sends the Google ID token to platform-spine, which verifies
// it and returns our own session token. role is only used when this creates a
// new account; without it a first-time Google user gets code ROLE_REQUIRED.
export async function googleLogin(platformSpineUrl, idToken, role) {
  return requestJson(platformSpineUrl, "/v1/auth/google", {
    method: "POST",
    body: { id_token: idToken, role: role || undefined },
    fallbackMessage: "Google sign-in failed. Please try again.",
  });
}
