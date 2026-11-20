#!/usr/bin/env python3
"""Apply the Borewell native API-resilience patch against the current main layout.

This patch intentionally does not touch screens/contractor/FindRigs.js. The
previous patch incorrectly assumed an anchor in that file; this version uses
only the current API client, auth helpers, and loader hook.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path.cwd()
APP = ROOT / "apps" / "borewell-native"
PLATFORM = APP / "services" / "platform.js"
AUTH = APP / "services" / "auth.js"
HOOKS = APP / "lib" / "hooks.js"
HTTP = APP / "services" / "http.js"

HTTP_SOURCE = r'''/**
 * Shared JSON transport for the native app's four backend services.
 *
 * Keep this dependency-free and keep the API contract details in
 * packages/contracts/openapi/*.yaml. Mutating requests are never retried.
 * Timeout/retry behaviour is intentionally not added here until the app's
 * Expo SDK 57 fetch implementation is verified on a physical Android device.
 */
export class ApiError extends Error {
  constructor(message, { code = null, status = null, fieldErrors = {}, cause = null } = {}) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.fieldErrors = fieldErrors;
    if (cause) this.cause = cause;
  }
}

const FIELD_LABELS = {
  email: "Email",
  password: "Password",
  phone: "Phone",
  role: "Account type",
  lat: "Latitude",
  lng: "Longitude",
};

function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function validationIssues(payload) {
  if (Array.isArray(payload?.detail)) return payload.detail;
  if (Array.isArray(payload?.error?.details)) return payload.error.details;
  if (Array.isArray(payload?.errors)) return payload.errors;
  return [];
}

function issueField(issue) {
  if (!Array.isArray(issue?.loc)) return "";
  const parts = issue.loc.filter((part) => !["body", "query", "path", "header"].includes(String(part)));
  return parts.length ? String(parts[parts.length - 1]) : "";
}

function issueMessage(issue) {
  const raw = String(issue?.msg || issue?.message || "").trim();
  if (raw) {
    return raw
      .replace(/^value error\s*[:,]?\s*/i, "")
      .replace(/^assertion error\s*[:,]?\s*/i, "")
      .replace(/\s+/g, " ");
  }

  const type = String(issue?.type || "").toLowerCase();
  if (type.includes("too_short")) return "is too short";
  if (type.includes("too_long")) return "is too long";
  if (type.includes("email")) return "is not a valid email address";
  if (type.includes("missing")) return "is required";
  return "is not valid";
}

function buildFieldErrors(issues) {
  const fields = {};
  for (const issue of issues) {
    const field = issueField(issue);
    if (field && !fields[field]) fields[field] = issueMessage(issue);
  }
  return fields;
}

function formatValidationSummary(issues) {
  const parts = issues.slice(0, 3).map((issue) => {
    const field = issueField(issue);
    const label = FIELD_LABELS[field] || (field ? field.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase()) : "Input");
    return `${label}: ${issueMessage(issue)}`;
  });
  return parts.join("; ");
}

export function makeApiError(payload, status, fallbackMessage = "The request could not be completed.") {
  const errorPayload = isObject(payload?.error) ? payload.error : {};
  const issues = validationIssues(payload);
  const fieldErrors = buildFieldErrors(issues);
  const serverMessage =
    (typeof errorPayload.message === "string" && errorPayload.message.trim()) ||
    (typeof payload?.detail === "string" && payload.detail.trim()) ||
    (typeof payload?.message === "string" && payload.message.trim()) ||
    "";

  let message;
  if (status >= 500) {
    // Do not expose an internal traceback or implementation detail to users.
    message = "The service is temporarily unavailable. Please try again shortly.";
  } else if (status === 422 && issues.length) {
    const summary = formatValidationSummary(issues);
    message = summary ? `Please check your details: ${summary}.` : "Please check the information you entered.";
  } else if (serverMessage) {
    message = serverMessage;
  } else if (status === 403) {
    message = "You do not have permission to perform this action.";
  } else if (status === 401) {
    message = "Your sign-in could not be verified. Check your credentials and try again.";
  } else {
    message = fallbackMessage;
  }

  return new ApiError(message, {
    code: typeof errorPayload.code === "string" ? errorPayload.code : null,
    status,
    fieldErrors,
  });
}

/** Send one JSON request and return the decoded JSON body. */
export async function requestJson(
  baseUrl,
  path,
  { method = "GET", token, body, headers: extraHeaders = {}, fallbackMessage } = {}
) {
  const requestMethod = String(method).toUpperCase();
  const headers = { Accept: "application/json", "Content-Type": "application/json", ...extraHeaders };
  if (token) headers.Authorization = `Bearer ${token}`;

  let response;
  try {
    response = await fetch(`${baseUrl}${path}`, {
      method: requestMethod,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch (cause) {
    const aborted = cause?.name === "AbortError" || /abort/i.test(String(cause?.message || ""));
    throw new ApiError(
      aborted
        ? "The request was cancelled. Please try again."
        : "Could not connect to Borewell. Check your internet connection and try again.",
      { code: aborted ? "REQUEST_ABORTED" : "NETWORK_ERROR", cause }
    );
  }

  let data = {};
  try {
    data = await response.json();
  } catch {
    // Empty or non-JSON bodies are valid for some HTTP responses. The status
    // code remains authoritative; malformed success bodies become an empty
    // object, matching the previous native client behaviour.
    data = {};
  }

  if (!response.ok) {
    throw makeApiError(data, response.status, fallbackMessage);
  }
  return data;
}
'''

PLATFORM_IMPORT_ANCHOR = " */\n\nexport const PLATFORM_SPINE_URL ="
PLATFORM_IMPORT_REPLACEMENT = " */\n\nimport { requestJson } from \"./http\";\n\nexport const PLATFORM_SPINE_URL ="

PLATFORM_REQUEST_OLD = '''async function request(baseUrl, path, { method = "GET", token, body } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${baseUrl}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const err = new Error(data?.error?.message || `Request failed (${response.status})`);
    err.code = data?.error?.code;
    err.status = response.status;
    throw err;
  }
  return data;
}'''
PLATFORM_REQUEST_NEW = "const request = requestJson;"

AUTH_IMPORT_ANCHOR = " */\n\nfunction base64UrlDecode(base64url) {"
AUTH_IMPORT_REPLACEMENT = " */\n\nimport { requestJson } from \"./http\";\n\nfunction base64UrlDecode(base64url) {"

AUTH_OLD = '''export async function login(platformSpineUrl, email, password) {
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

// Google sign-in: sends the Google ID token to platform-spine, which verifies
// it and returns our own session token. role is only used when this creates a
// new account; without it a first-time Google user gets code ROLE_REQUIRED.
export async function googleLogin(platformSpineUrl, idToken, role) {
  const response = await fetch(`${platformSpineUrl}/v1/auth/google`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id_token: idToken, role: role || undefined }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const err = new Error(body?.error?.message || "Google sign-in failed");
    err.code = body?.error?.code;
    throw err;
  }
  return response.json(); // { access_token, role, new_account }
}'''
AUTH_NEW = '''export async function login(platformSpineUrl, email, password) {
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
}'''

HOOKS_OLD = '''export function useLoad(loader, deps = [], { pollMs } = {}) {
  const [state, setState] = useState({ data: undefined, error: null, loading: true });
  const mounted = useRef(true);
  const loaderRef = useRef(loader);
  loaderRef.current = loader;

  const run = useCallback(async ({ quiet = false } = {}) => {
    if (!quiet) setState((s) => ({ ...s, loading: true }));
    try {
      const data = await loaderRef.current();
      if (mounted.current) setState({ data, error: null, loading: false });
      return data;
    } catch (err) {
      if (mounted.current) setState((s) => ({ data: s.data, error: err, loading: false }));
      return undefined;
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    run();
    return () => { mounted.current = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    if (!pollMs) return undefined;
    // There are no websockets or push notifications in the backend yet (see
    // docs/adr/0005-field-console-ui.md's API gaps) - screens that need to
    // see a change made by someone else poll on a slow interval.
    let id = setInterval(() => run({ quiet: true }), pollMs);
    const sub = AppState.addEventListener("change", (next) => {
      clearInterval(id);
      if (next === "active") {
        run({ quiet: true });
        id = setInterval(() => run({ quiet: true }), pollMs);
      }
    });
    return () => { clearInterval(id); sub.remove(); };
  }, [pollMs, run]);

  return { ...state, reload: run };
}'''
HOOKS_NEW = '''export function useLoad(loader, deps = [], { pollMs } = {}) {
  const [state, setState] = useState({ data: undefined, error: null, loading: true });
  const mounted = useRef(false);
  const requestVersion = useRef(0);
  const loaderRef = useRef(loader);
  loaderRef.current = loader;

  const run = useCallback(async ({ quiet = false } = {}) => {
    const version = ++requestVersion.current;
    if (!quiet) setState((s) => ({ ...s, loading: true }));
    try {
      const data = await loaderRef.current();
      if (mounted.current && version === requestVersion.current) {
        setState({ data, error: null, loading: false });
      }
      return data;
    } catch (err) {
      if (mounted.current && version === requestVersion.current) {
        // Retain the last successful data. Screens can show it with the
        // error message rather than replacing a populated view with a blank.
        setState((s) => ({ data: s.data, error: err, loading: false }));
      }
      return undefined;
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    run();
    return () => {
      mounted.current = false;
      // Ignore any request still in flight when dependencies change or the
      // component unmounts; an older response must not overwrite newer data.
      requestVersion.current += 1;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    if (!pollMs) return undefined;
    // There are no websockets or push notifications in the backend yet (see
    // docs/adr/0005-field-console-ui.md's API gaps) - screens that need to
    // see a change made by someone else poll on a slow interval.
    let id = setInterval(() => run({ quiet: true }), pollMs);
    const sub = AppState.addEventListener("change", (next) => {
      clearInterval(id);
      if (next === "active") {
        run({ quiet: true });
        id = setInterval(() => run({ quiet: true }), pollMs);
      }
    });
    return () => { clearInterval(id); sub.remove(); };
  }, [pollMs, run]);

  return {
    ...state,
    isStale: state.data !== undefined && state.error !== null,
    reload: run,
  };
}'''


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def replace_once(content: str, old: str, new: str, label: str) -> str:
    count = content.count(old)
    if count != 1:
        fail(f"Expected exactly one {label} anchor; found {count}. No files were written.")
    return content.replace(old, new, 1)


def git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True)
    if result.returncode != 0:
        fail(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout.strip()


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    os.replace(temporary, path)


def main() -> None:
    if not (ROOT / ".git").exists() or not APP.is_dir():
        fail("Run this script from the root of the borewell-platform Git repository.")

    branch = git("branch", "--show-current")
    if branch in {"main", "master"}:
        fail("You are on the protected main branch. First run: git switch -c feature/phase1-api-resilience")

    if HTTP.exists():
        fail(f"{HTTP.relative_to(ROOT)} already exists. Review it manually; no files were written.")

    targets = [PLATFORM, AUTH, HOOKS]
    for path in targets:
        if not path.is_file():
            fail(f"Required file is missing: {path.relative_to(ROOT)}")
        rel = str(path.relative_to(ROOT))
        if subprocess.run(["git", "diff", "--quiet", "--", rel], cwd=ROOT).returncode != 0:
            fail(f"{rel} has unstaged edits. Commit or stash them before applying this patch.")
        if subprocess.run(["git", "diff", "--cached", "--quiet", "--", rel], cwd=ROOT).returncode != 0:
            fail(f"{rel} has staged edits. Commit or unstage them before applying this patch.")

    # Prepare every replacement in memory first. If any anchor differs, the
    # script exits before touching any source file.
    platform_text = PLATFORM.read_text(encoding="utf-8")
    auth_text = AUTH.read_text(encoding="utf-8")
    hooks_text = HOOKS.read_text(encoding="utf-8")

    platform_text = replace_once(platform_text, PLATFORM_IMPORT_ANCHOR, PLATFORM_IMPORT_REPLACEMENT, "platform import")
    platform_text = replace_once(platform_text, PLATFORM_REQUEST_OLD, PLATFORM_REQUEST_NEW, "platform request helper")
    auth_text = replace_once(auth_text, AUTH_IMPORT_ANCHOR, AUTH_IMPORT_REPLACEMENT, "auth import")
    auth_text = replace_once(auth_text, AUTH_OLD, AUTH_NEW, "auth request functions")
    hooks_text = replace_once(hooks_text, HOOKS_OLD, HOOKS_NEW, "useLoad hook")

    # All anchors were verified. Write only these four files.
    atomic_write(HTTP, HTTP_SOURCE)
    atomic_write(PLATFORM, platform_text)
    atomic_write(AUTH, auth_text)
    atomic_write(HOOKS, hooks_text)

    print("Phase 1 patch applied on branch:", branch)
    print("Changed files:")
    for path in [HTTP, PLATFORM, AUTH, HOOKS]:
        print("  ", path.relative_to(ROOT))
    print("No screens, map files, backend services, contracts, workflows, secrets, or production resources were changed.")
    print("No dependencies were added. No commit, push, deployment, or APK build was performed.")
    print("Next: inspect `git diff --check` and `git diff` before running the native app checks.")


if __name__ == "__main__":
    main()
