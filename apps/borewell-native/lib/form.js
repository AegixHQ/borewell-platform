/**
 * Form helpers shared by every screen with inputs: validation that matches
 * what the backend enforces (so a typo is caught before a round trip, and the
 * message is the same either way), and keyboard flow - Next moves to the next
 * field, Done on the last field submits.
 *
 * The backend stays the authority: these only save the user a failed request.
 */
import { createRef, useState } from "react";

// Pragmatic, not RFC-complete: one @, a dotted domain, no spaces, no empty or
// doubled dots. The server runs the full email-validator check.
const EMAIL_RE = /^[^\s@.]+(\.[^\s@.]+)*@[^\s@.]+(\.[^\s@.]+)*\.[^\s@.]{2,}$/;

export function normaliseEmail(value) {
  return String(value ?? "").trim().toLowerCase();
}

/** Returns an error message, or null when the email looks valid. */
export function emailError(value) {
  const email = normaliseEmail(value);
  if (!email) return "Enter an email address.";
  if (email.length > 254 || !EMAIL_RE.test(email)) return "Enter a valid email address, like name@example.com.";
  return null;
}

/** Same limits as the backend: 8+ characters, at most 72 bytes (bcrypt). */
export function passwordError(value) {
  const password = String(value ?? "");
  if (password.length < 8) return "Use at least 8 characters.";
  if (new TextEncoder().encode(password).length > 72) return "Use at most 72 characters.";
  return null;
}

/** Optional 10-digit Indian mobile, with or without +91. Empty is fine. */
export function phoneError(value) {
  const raw = String(value ?? "").trim();
  if (!raw) return null;
  const digits = raw.replace("+91", "").replace(/[\s-]/g, "");
  return /^\d{10}$/.test(digits) ? null : "Enter a 10-digit mobile number.";
}

/** A password an admin can hand to a new contractor: no look-alike characters. */
export function generatePassword(length = 12) {
  const alphabet = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789";
  let out = "";
  for (let i = 0; i < length; i += 1) out += alphabet[Math.floor(Math.random() * alphabet.length)];
  return out;
}

/**
 * Throws when any value in `errors` ({ field: message | null }) is set, in the
 * shape useAction's run() already understands: the message lands in the alert
 * and each field's message under its input.
 */
export function assertValid(errors) {
  const failed = Object.entries(errors).filter(([, message]) => message);
  if (!failed.length) return;
  const err = new Error("Please fix the highlighted fields.");
  err.fieldErrors = Object.fromEntries(failed);
  throw err;
}

/** One stable ref per field, in tab order. */
export function useFieldRefs(count) {
  const [refs] = useState(() => Array.from({ length: count }, () => createRef()));
  return refs;
}

/**
 * Props that wire field `index` into the chain: spread them onto <Input>.
 * The last field shows "Done" and calls onSubmit; the others show "Next".
 * Not for multiline inputs, where Enter must stay a newline.
 */
export function chain(refs, index, onSubmit) {
  const last = index === refs.length - 1;
  return {
    ref: refs[index],
    returnKeyType: last ? "done" : "next",
    submitBehavior: last ? "blurAndSubmit" : "submit",
    onSubmitEditing: last ? onSubmit : () => refs[index + 1].current?.focus(),
  };
}
