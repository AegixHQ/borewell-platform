#!/usr/bin/env python3
"""Apply Borewell Phase 1 native API/error-handling changes on a feature branch.

Run from the borewell-platform repository root after updating main. The script
creates its own feature branch and refuses to edit an existing dirty tree or
main. It does not deploy, touch .env.prod, access the database, or rebuild an APK.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path.cwd()
BRANCH = "phase1/native-api-resilience"
PLANNED_FILES: dict[str, str] = {}
NEW_FILES: dict[str, str] = {}
CREATE_BRANCH = False


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    content = PLANNED_FILES.get(path, target.read_text())
    count = content.count(old)
    if count != 1:
        raise RuntimeError(f"Expected exactly one replacement anchor in {path}; found {count}. No files were written.")
    PLANNED_FILES[path] = content.replace(old, new, 1)


def add_file(path: str, content: str) -> None:
    target = ROOT / path
    if target.exists():
        if target.read_text() != content:
            raise RuntimeError(f"Refusing to overwrite existing file: {path}")
        return
    NEW_FILES[path] = content


def prepare_branch() -> None:
    global CREATE_BRANCH
    if not (ROOT / "apps/borewell-native/services/platform.js").exists():
        raise RuntimeError("Run this script from the borewell-platform repository root.")
    if git("status", "--porcelain"):
        raise RuntimeError("Working tree is not clean. Commit or stash existing work before running this script.")
    current = git("branch", "--show-current")
    if current == "main":
        CREATE_BRANCH = True
    elif current != BRANCH:
        raise RuntimeError(f"Expected main or {BRANCH}; current branch is {current!r}.")


def write_changes() -> None:
    # All text anchors are validated before this function is called, so a
    # mismatch cannot leave a half-applied patch in the working tree.
    if CREATE_BRANCH:
        subprocess.check_call(["git", "switch", "-c", BRANCH], cwd=ROOT)
    for path, content in PLANNED_FILES.items():
        (ROOT / path).write_text(content)
    for path, content in NEW_FILES.items():
        target = ROOT / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)


API_JS = r'''const DEFAULT_TIMEOUT_MS = 15000;
const DEFAULT_GET_RETRIES = 1;
const TRANSIENT_HTTP_STATUSES = new Set([408, 502, 503, 504]);

function friendlyMessage({ code, status, kind, message, name } = {}) {
  if (kind === "timeout" || code === "REQUEST_TIMEOUT") {
    return "The request took too long. Check your connection and try again.";
  }
  if (kind === "network" || code === "NETWORK_ERROR" || name === "TypeError") {
    return "Couldn't reach Borewell. Check your internet connection and try again.";
  }
  if (code === "VALIDATION_ERROR" || status === 422) {
    return "Some details need attention. Check the form and try again.";
  }
  if (status === 429) {
    return "Too many attempts. Please wait a little and try again.";
  }
  if (status >= 500) {
    return "Borewell is temporarily unavailable. Please try again shortly.";
  }
  return message || "Something went wrong. Please try again.";
}

export class ApiError extends Error {
  constructor({ message, code, status, traceId, retryAfterMs, kind = "http", cause } = {}) {
    super(friendlyMessage({ message, code, status, kind, name: cause?.name }));
    this.name = "ApiError";
    this.code = code || "REQUEST_FAILED";
    this.status = status ?? null;
    this.traceId = traceId ?? null;
    this.retryAfterMs = retryAfterMs ?? null;
    this.kind = kind;
    this.serverMessage = message ?? null;
    if (cause !== undefined) this.cause = cause;
  }
}

export function getUserFacingMessage(error) {
  if (typeof error === "string") return error;
  if (error instanceof ApiError) return error.message;
  return friendlyMessage({
    code: error?.code,
    status: error?.status,
    kind: error?.kind,
    message: error?.message,
    name: error?.name,
  });
}

function parseRetryAfter(value) {
  if (!value) return null;
  const seconds = Number(value);
  if (Number.isFinite(seconds)) return Math.max(0, seconds * 1000);
  const date = Date.parse(value);
  return Number.isNaN(date) ? null : Math.max(0, date - Date.now());
}

function responseError(response, payload) {
  const body = payload?.error || payload || {};
  return new ApiError({
    message: body?.message || payload?.detail || `Request failed (${response.status})`,
    code: body?.code || "HTTP_ERROR",
    status: response.status,
    traceId: body?.trace_id || payload?.trace_id,
    retryAfterMs: parseRetryAfter(response.headers?.get?.("Retry-After")),
  });
}

function shouldRetry(error, method, attempt, maxRetries) {
  if (method !== "GET" || attempt >= maxRetries) return false;
  if (error.retryAfterMs !== null && error.retryAfterMs > 3000) return false;
  return error.kind === "network" || error.kind === "timeout" || TRANSIENT_HTTP_STATUSES.has(error.status);
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Shared JSON transport for every native API call, including authentication.
 * Only GET requests are retried; mutations (especially payments and bookings)
 * are never replayed automatically.
 */
export async function apiRequest(baseUrl, path, {
  method = "GET",
  token,
  body,
  timeoutMs = DEFAULT_TIMEOUT_MS,
  retries,
} = {}) {
  if (!baseUrl) {
    throw new ApiError({ code: "API_URL_MISSING", kind: "configuration", message: "The API address is not configured." });
  }

  const verb = String(method).toUpperCase();
  const maxRetries = verb === "GET"
    ? Math.max(0, Math.floor(retries ?? DEFAULT_GET_RETRIES))
    : 0;
  const url = `${String(baseUrl).replace(/\/+$/, "")}/${String(path).replace(/^\/+/, "")}`;
  const headers = { Accept: "application/json", "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;

  for (let attempt = 0; ; attempt += 1) {
    const controller = new AbortController();
    let timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, Math.max(1, Number(timeoutMs) || DEFAULT_TIMEOUT_MS));

    try {
      const response = await fetch(url, {
        method: verb,
        headers,
        body: body !== undefined ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      });
      const raw = await response.text();
      let payload = {};
      if (raw) {
        try {
          payload = JSON.parse(raw);
        } catch {
          payload = null;
        }
      }

      if (!response.ok) throw responseError(response, payload);
      if (payload === null) {
        throw new ApiError({
          code: "INVALID_RESPONSE",
          status: response.status,
          kind: "response",
          message: "The server returned a response the app could not read.",
        });
      }
      return payload;
    } catch (cause) {
      let error;
      if (cause instanceof ApiError) {
        error = cause;
      } else if (timedOut) {
        error = new ApiError({ code: "REQUEST_TIMEOUT", kind: "timeout", cause });
      } else {
        error = new ApiError({ code: "NETWORK_ERROR", kind: "network", cause });
      }

      if (shouldRetry(error, verb, attempt, maxRetries)) {
        const delayMs = error.retryAfterMs ?? Math.min(300 * (attempt + 1), 1000);
        await wait(delayMs);
        continue;
      }
      throw error;
    } finally {
      clearTimeout(timer);
    }
  }
}
'''

API_TEST = r'''import assert from "node:assert/strict";
import { afterEach, test } from "node:test";
import { ApiError, apiRequest } from "./api.js";

const originalFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = originalFetch; });

function response(status, payload, headers = {}) {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: (name) => headers[name] ?? headers[name.toLowerCase()] ?? null },
    text: async () => payload === undefined ? "" : JSON.stringify(payload),
  };
}

test("sends a bearer token and JSON body, then parses the response", async () => {
  let captured;
  globalThis.fetch = async (url, options) => {
    captured = { url, options };
    return response(201, { job_id: "job-1" });
  };

  const result = await apiRequest("https://api.example.test/", "/v1/jobs", {
    method: "POST",
    token: "test-token",
    body: { job_type: "residential" },
  });

  assert.deepEqual(result, { job_id: "job-1" });
  assert.equal(captured.url, "https://api.example.test/v1/jobs");
  assert.equal(captured.options.headers.Authorization, "Bearer test-token");
  assert.equal(captured.options.body, JSON.stringify({ job_type: "residential" }));
});

test("normalizes validation errors and retains the trace ID", async () => {
  globalThis.fetch = async () => response(422, {
    error: { code: "VALIDATION_ERROR", message: "raw pydantic detail", trace_id: "trace-123" },
  });

  await assert.rejects(
    apiRequest("https://api.example.test", "/v1/auth/register", { method: "POST", body: {} }),
    (error) => {
      assert.ok(error instanceof ApiError);
      assert.equal(error.code, "VALIDATION_ERROR");
      assert.equal(error.status, 422);
      assert.equal(error.traceId, "trace-123");
      assert.equal(error.message, "Some details need attention. Check the form and try again.");
      return true;
    }
  );
});

test("retries a transient GET once", async () => {
  let calls = 0;
  globalThis.fetch = async () => {
    calls += 1;
    return calls === 1 ? response(503, { error: { message: "temporarily unavailable" } }) : response(200, []);
  };

  const result = await apiRequest("https://api.example.test", "/v1/jobs", { timeoutMs: 1000 });
  assert.deepEqual(result, []);
  assert.equal(calls, 2);
});

test("does not retry a mutating POST", async () => {
  let calls = 0;
  globalThis.fetch = async () => {
    calls += 1;
    return response(503, { error: { message: "temporarily unavailable" } });
  };

  await assert.rejects(apiRequest("https://api.example.test", "/v1/payments", { method: "POST", body: {} }));
  assert.equal(calls, 1);
});

test("turns a timed-out request into a readable timeout error", async () => {
  globalThis.fetch = (_url, { signal }) => new Promise((_resolve, reject) => {
    signal.addEventListener("abort", () => {
      const error = new Error("aborted");
      error.name = "AbortError";
      reject(error);
    }, { once: true });
  });

  await assert.rejects(
    apiRequest("https://api.example.test", "/v1/auth/login", { method: "POST", body: {}, timeoutMs: 5 }),
    (error) => error.code === "REQUEST_TIMEOUT" && error.message.includes("took too long")
  );
});

test("does not automatically retry rate-limited requests", async () => {
  let calls = 0;
  globalThis.fetch = async () => {
    calls += 1;
    return response(429, { error: { code: "RATE_LIMITED", message: "slow down" } }, { "Retry-After": "2" });
  };

  await assert.rejects(
    apiRequest("https://api.example.test", "/v1/jobs"),
    (error) => error.status === 429 && error.retryAfterMs === 2000
  );
  assert.equal(calls, 1);
});
'''

prepare_branch()

# New shared transport and focused dependency-free Node tests.
add_file("apps/borewell-native/services/api.js", API_JS)
add_file("apps/borewell-native/services/api.test.js", API_TEST)

# Keep the native API operations on one transport. The native transport is
# intentionally separate from shared-ui because Expo SDK 57 has its own global
# fetch implementation and build-time switch.
replace_once(
    "apps/borewell-native/services/platform.js",
    " * Every function body below is copied verbatim from shared-ui/platform.js\n * - confirmed there is no browser-only API anywhere in it (no window,\n * document, localStorage) before porting, so this was a mechanical copy,\n * not a rewrite. The ONLY real adaptation is the env var section below:\n",
    " * Endpoint functions below remain hand-synchronised with shared-ui. The\n * transport is native-specific so timeouts, structured errors and safe GET\n * retries can be tested without bringing a browser runtime into Expo.\n",
)
replace_once(
    "apps/borewell-native/services/platform.js",
    "export const PLATFORM_SPINE_URL =\n",
    'import { apiRequest } from "./api";\n\nexport const PLATFORM_SPINE_URL =\n',
)
replace_once(
    "apps/borewell-native/services/platform.js",
    '''async function request(baseUrl, path, { method = "GET", token, body } = {}) {
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
}
''',
    "const request = apiRequest;\n",
)

# Authentication must use the same transport and preserve API error metadata.
replace_once(
    "apps/borewell-native/services/auth.js",
    "function base64UrlDecode(base64url) {\n",
    'import { apiRequest } from "./api";\n\nfunction base64UrlDecode(base64url) {\n',
)
replace_once(
    "apps/borewell-native/services/auth.js",
    '''export async function login(platformSpineUrl, email, password) {
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
''',
    '''export async function login(platformSpineUrl, email, password) {
  return apiRequest(platformSpineUrl, "/v1/auth/login", {
    method: "POST",
    body: { email, password },
  }); // { access_token, role }
}
''',
)
replace_once(
    "apps/borewell-native/services/auth.js",
    '''export async function registerAccount(platformSpineUrl, { email, password, phone, role }) {
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
''',
    '''export async function registerAccount(platformSpineUrl, { email, password, phone, role }) {
  return apiRequest(platformSpineUrl, "/v1/auth/register", {
    method: "POST",
    body: { email, password, phone: phone || undefined, role },
  }); // { access_token, role }
}
''',
)
replace_once(
    "apps/borewell-native/services/auth.js",
    '''export async function googleLogin(platformSpineUrl, idToken, role) {
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
}
''',
    '''export async function googleLogin(platformSpineUrl, idToken, role) {
  return apiRequest(platformSpineUrl, "/v1/auth/google", {
    method: "POST",
    body: { id_token: idToken, role: role || undefined },
  }); // { access_token, role, new_account }
}
''',
)

# Preserve existing data on refresh, ignore stale responses, and normalize
# errors without changing the hook's existing data/error/loading contract.
replace_once(
    "apps/borewell-native/lib/hooks.js",
    'import { RESOURCE_NETWORK_URL, lookupServiceArea } from "../services/platform";\n',
    'import { RESOURCE_NETWORK_URL, lookupServiceArea } from "../services/platform";\nimport { getUserFacingMessage } from "../services/api";\n',
)
replace_once(
    "apps/borewell-native/lib/hooks.js",
    '''export function useLoad(loader, deps = [], { pollMs } = {}) {
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
''',
    '''export function useLoad(loader, deps = [], { pollMs } = {}) {
  const [state, setState] = useState({ data: undefined, error: null, loading: true, refreshing: false });
  const mounted = useRef(false);
  const requestId = useRef(0);
  const loaderRef = useRef(loader);
  loaderRef.current = loader;

  const run = useCallback(async ({ quiet = false } = {}) => {
    const currentRequest = ++requestId.current;
    if (!quiet) {
      setState((s) => ({
        ...s,
        loading: s.data === undefined,
        refreshing: s.data !== undefined,
        error: null,
      }));
    }
    try {
      const data = await loaderRef.current();
      if (mounted.current && currentRequest === requestId.current) {
        setState({ data, error: null, loading: false, refreshing: false });
      }
      return data;
    } catch (err) {
      if (mounted.current && currentRequest === requestId.current) {
        const safeError = err instanceof Error ? err : new Error(getUserFacingMessage(err));
        setState((s) => ({ ...s, error: safeError, loading: false, refreshing: false }));
      }
      return undefined;
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    run();
    return () => {
      mounted.current = false;
      requestId.current += 1;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
''',
)
replace_once(
    "apps/borewell-native/lib/hooks.js",
    '      setError(onError ? onError(err) : err.message);\n',
    '      setError(onError ? onError(err) : getUserFacingMessage(err));\n',
)

# Add simple, client-side registration validation so routine input mistakes
# are shown next to their fields rather than as backend/Pydantic internals.
replace_once(
    "apps/borewell-native/screens/AuthScreen.js",
    'const ROLE_OPTIONS = [\n',
    '''function validateAuthForm({ registering, email, password, phone }) {
  const errors = {};
  const cleanEmail = String(email || "").trim();
  if (!cleanEmail) errors.email = "Enter your email address.";
  else if (!/^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/.test(cleanEmail)) errors.email = "Enter a valid email address.";

  if (!password) errors.password = "Enter your password.";
  else if (registering && Array.from(password).length < 8) errors.password = "Use at least 8 characters.";
  else if (registering && Array.from(password).length > 128) errors.password = "Use no more than 128 characters.";
  else if (registering && new TextEncoder().encode(password).length > 72) errors.password = "Use a password no longer than 72 UTF-8 bytes.";

  if (registering && String(phone || "").trim()) {
    const digits = String(phone).trim().replace(/[\\s-]/g, "").replace(/^\\+91/, "");
    if (!/^\\d{10}$/.test(digits)) errors.phone = "Enter a 10-digit Indian mobile number, optionally prefixed by +91.";
  }
  return errors;
}

const ROLE_OPTIONS = [
''',
)
replace_once(
    "apps/borewell-native/screens/AuthScreen.js",
    '  const [notice, setNotice] = useState(null);\n',
    '  const [notice, setNotice] = useState(null);\n  const [fieldErrors, setFieldErrors] = useState({});\n',
)
replace_once(
    "apps/borewell-native/screens/AuthScreen.js",
    '''  async function submit() {
    await run(async () => {
      const { access_token: token } = registering
        ? await registerAccount(PLATFORM_SPINE_URL, { email, password, phone, role })
        : await login(PLATFORM_SPINE_URL, email, password);
      await signIn({ token, email });
    });
  }
''',
    '''  async function submit() {
    const validation = validateAuthForm({ registering, email, password, phone });
    setFieldErrors(validation);
    if (Object.keys(validation).length) return;

    const cleanEmail = email.trim();
    await run(async () => {
      const { access_token: token } = registering
        ? await registerAccount(PLATFORM_SPINE_URL, { email: cleanEmail, password, phone: phone.trim(), role })
        : await login(PLATFORM_SPINE_URL, cleanEmail, password);
      await signIn({ token, email: cleanEmail });
    });
  }
''',
)
replace_once(
    "apps/borewell-native/screens/AuthScreen.js",
    '''          <Pills
            value={mode}
            onChange={setMode}
            options={[{ value: "login", label: "Sign in" }, { value: "register", label: "Create account" }]}
          />
''',
    '''          <Pills
            value={mode}
            onChange={(value) => { setMode(value); setFieldErrors({}); }}
            options={[{ value: "login", label: "Sign in" }, { value: "register", label: "Create account" }]}
          />
''',
)
replace_once(
    "apps/borewell-native/screens/AuthScreen.js",
    '''          <Field label="Email">
            <Input
              value={email}
              onChangeText={setEmail}
''',
    '''          <Field label="Email" error={fieldErrors.email}>
            <Input
              value={email}
              onChangeText={(value) => { setEmail(value); setFieldErrors((current) => ({ ...current, email: undefined })); }}
''',
)
replace_once(
    "apps/borewell-native/screens/AuthScreen.js",
    '''            <Field label="Phone" hint="Optional">
              <Input value={phone} onChangeText={setPhone} placeholder="+91 " keyboardType="phone-pad" />
            </Field>
''',
    '''            <Field label="Phone" hint="Optional · 10-digit Indian mobile number" error={fieldErrors.phone}>
              <Input
                value={phone}
                onChangeText={(value) => { setPhone(value); setFieldErrors((current) => ({ ...current, phone: undefined })); }}
                placeholder="+91 "
                keyboardType="phone-pad"
              />
            </Field>
''',
)
replace_once(
    "apps/borewell-native/screens/AuthScreen.js",
    '''          <Field label="Password" hint={registering ? "At least 8 characters" : undefined}>
            <Input
              value={password}
              onChangeText={setPassword}
''',
    '''          <Field label="Password" hint={registering ? "At least 8 characters" : undefined} error={fieldErrors.password}>
            <Input
              value={password}
              onChangeText={(value) => { setPassword(value); setFieldErrors((current) => ({ ...current, password: undefined })); }}
''',
)

# A consistent retry notice for list/detail fetches. Existing cards and data
# remain on screen after a refresh failure; the notice explains that they are
# stale and provides an explicit retry button.
replace_once(
    "apps/borewell-native/components/ui.js",
    'export function EmptyState({ title, children, action }) {\n',
    '''export function LoadError({ error, onRetry, stale = false }) {
  if (!error) return null;
  return (
    <View style={{ gap: 8 }}>
      <Alert>
        {error.message || "Couldn't load this information. Please try again."}
        {stale ? " Previously loaded information is still shown." : ""}
      </Alert>
      {onRetry && <Button title="Try again" variant="light" size="sm" onPress={onRetry} />}
    </View>
  );
}

export function EmptyState({ title, children, action }) {
''',
)

# Update screen imports and existing fetch-error alerts to use the shared
# retry affordance. These are all consumers of useLoad in the native app.
screen_updates = [
    ("apps/borewell-native/screens/customer/CustomerHome.js",
     'Alert, Badge, Body, Button, Card, EmptyState, Icon, JobTypeIcon, Loading, Row, Screen, Tile, Title,',
     'Alert, Badge, Body, Button, Card, EmptyState, Icon, JobTypeIcon, Loading, LoadError, Row, Screen, Tile, Title,',
     '{!!jobs.error && <Alert>{jobs.error.message}</Alert>}',
     '<LoadError error={jobs.error} onRetry={() => jobs.reload()} stale={jobs.data !== undefined} />'),
    ("apps/borewell-native/screens/contractor/ContractorBoard.js",
     'Loading, Pills, Row, Screen, Tile,',
     'Loading, LoadError, Pills, Row, Screen, Tile,',
     '{!!jobs.error && <Alert>{jobs.error.message}</Alert>}',
     '<LoadError error={jobs.error} onRetry={() => jobs.reload()} stale={jobs.data !== undefined} />'),
    ("apps/borewell-native/screens/contractor/FindRigs.js",
     'Loading, Pills, Row, Screen, Sheet, Tile, Toast,',
     'Loading, LoadError, Pills, Row, Screen, Sheet, Tile, Toast,',
     '{!!jobs.error && <Alert>{jobs.error.message}</Alert>}',
     '<LoadError error={jobs.error} onRetry={() => jobs.reload()} stale={jobs.data !== undefined} />'),
    ("apps/borewell-native/screens/contractor/Bookings.js",
     'Alert, Badge, Body, Card, EmptyState, Icon, Loading, Pills, Row, Screen, Tile,',
     'Alert, Badge, Body, Card, EmptyState, Icon, Loading, LoadError, Pills, Row, Screen, Tile,',
     '{!!bookings.error && <Alert>{bookings.error.message}</Alert>}',
     '<LoadError error={bookings.error} onRetry={() => bookings.reload()} stale={bookings.data !== undefined} />'),
    ("apps/borewell-native/screens/owner/OwnerRequests.js",
     'Loading, Pills, Row, Screen, Sheet, Tile, Title, Toast,',
     'Loading, LoadError, Pills, Row, Screen, Sheet, Tile, Title, Toast,',
     '{!!bookings.error && <Alert>{bookings.error.message}</Alert>}',
     '<LoadError error={bookings.error} onRetry={() => bookings.reload()} stale={bookings.data !== undefined} />'),
    ("apps/borewell-native/screens/owner/OwnerFleet.js",
     'Pills, Row, Screen, Sheet, Tile, Toast,',
     'LoadError, Pills, Row, Screen, Sheet, Tile, Toast,',
     '{!!resources.error && <Alert>{resources.error.message}</Alert>}',
     '<LoadError error={resources.error} onRetry={() => resources.reload()} stale={resources.data !== undefined} />'),
    ("apps/borewell-native/screens/contractor/Setup.js",
     'Input, Inset, Loading, Pills, Row, Screen, Tile, Title, Toast,',
     'Input, Inset, Loading, LoadError, Pills, Row, Screen, Tile, Title, Toast,',
     '{!!rules.error && <Alert>{rules.error.message}</Alert>}',
     '<LoadError error={rules.error} onRetry={() => rules.reload()} stale={rules.data !== undefined} />'),
    ("apps/borewell-native/screens/contractor/Setup.js",
     'Input, Inset, Loading, LoadError, Pills, Row, Screen, Tile, Title, Toast,',
     'Input, Inset, Loading, LoadError, Pills, Row, Screen, Tile, Title, Toast,',
     '{!!areas.error && <Alert>{areas.error.message}</Alert>}',
     '<LoadError error={areas.error} onRetry={() => areas.reload()} stale={areas.data !== undefined} />'),
    ("apps/borewell-native/screens/customer/CustomerJob.js",
     'KeyValue, Loading, Pills, Row, Screen, Title, Toast,',
     'KeyValue, Loading, LoadError, Pills, Row, Screen, Title, Toast,',
     '{!!action.error && <Alert>{action.error}</Alert>}',
     '{!!action.error && <Alert>{action.error}</Alert>}'),
    ("apps/borewell-native/screens/contractor/ContractorJob.js",
     'Inset, KeyValue, Loading, Row, Screen, Sheet, Title, Toast,',
     'Inset, KeyValue, Loading, LoadError, Row, Screen, Sheet, Title, Toast,',
     'if (job.error) {',
     'if (job.error && !job.data) {'),
]
for path, old_import, new_import, old_error, new_error in screen_updates:
    replace_once(path, old_import, new_import)
    replace_once(path, old_error, new_error)

# Surface secondary list/detail failures that affect summary figures and actions.
replace_once(
    "apps/borewell-native/screens/contractor/ContractorBoard.js",
    '''      <LoadError error={jobs.error} onRetry={() => jobs.reload()} stale={jobs.data !== undefined} />

      <Button title="New walk-in job" variant="saffron" trailing onPress={() => navigate("contractor.walkin")} />
''',
    '''      <LoadError error={jobs.error} onRetry={() => jobs.reload()} stale={jobs.data !== undefined} />
      <LoadError error={bookings.error} onRetry={() => bookings.reload()} stale={bookings.data !== undefined} />
      <LoadError error={quotes.error} onRetry={() => quotes.reload()} stale={quotes.data !== undefined} />

      <Button title="New walk-in job" variant="saffron" trailing onPress={() => navigate("contractor.walkin")} />
''',
)
replace_once(
    "apps/borewell-native/screens/contractor/ContractorBoard.js",
    '''        getLatestQuotationForJob(QUOTATION_URL, session.token, j.job_id)
          .then((q) => [j.job_id, q])
          .catch(() => [j.job_id, null])
''',
    '''        getLatestQuotationForJob(QUOTATION_URL, session.token, j.job_id)
          .then((q) => [j.job_id, q])
          .catch((err) => {
            if (err.code === "QUOTATION_NOT_FOUND" || err.status === 404) return [j.job_id, null];
            throw err;
          })
''',
)
replace_once(
    "apps/borewell-native/screens/contractor/FindRigs.js",
    '!!results.error && <Alert>{results.error.message}</Alert>',
    '<LoadError error={results.error} onRetry={() => results.reload()} stale={results.data !== undefined} />',
)
replace_once(
    "apps/borewell-native/screens/contractor/FindRigs.js",
    '''      <LoadError error={job.error} onRetry={() => job.reload()} stale={job.data !== undefined} />
      <Card style={{ padding: 0, overflow: "hidden" }}>
''',
    '''      <LoadError error={job.error} onRetry={() => job.reload()} stale={job.data !== undefined} />
      <LoadError error={bookings.error} onRetry={() => bookings.reload()} stale={bookings.data !== undefined} />
      <Card style={{ padding: 0, overflow: "hidden" }}>
''',
)
replace_once(
    "apps/borewell-native/screens/owner/OwnerRequests.js",
    '''      <LoadError error={bookings.error} onRetry={() => bookings.reload()} stale={bookings.data !== undefined} />

      <Card dark>
''',
    '''      <LoadError error={bookings.error} onRetry={() => bookings.reload()} stale={bookings.data !== undefined} />
      <LoadError error={resources.error} onRetry={() => resources.reload()} stale={resources.data !== undefined} />

      <Card dark>
''',
)

# The job-detail views should keep rendering their last successful data while
# showing a non-blocking retry notice if a background refresh fails.
replace_once(
    "apps/borewell-native/screens/customer/CustomerJob.js",
    '''      />

      <Card dark>
        <Eyebrow dark>Now</Eyebrow>
''',
    '''      />

      <LoadError error={job.error} onRetry={() => job.reload()} stale={job.data !== undefined} />
      <LoadError error={quote.error} onRetry={() => quote.reload()} stale={quote.data !== undefined} />
      <LoadError error={payments.error} onRetry={() => payments.reload()} stale={payments.data !== undefined} />
      <LoadError error={completion.error} onRetry={() => completion.reload()} stale={completion.data !== undefined} />
      <Card dark>
        <Eyebrow dark>Now</Eyebrow>
''',
)
replace_once(
    "apps/borewell-native/screens/customer/CustomerJob.js",
    'if (job.error) {',
    'if (job.error && !job.data) {',
)
replace_once(
    "apps/borewell-native/screens/contractor/ContractorJob.js",
    '''      />

      {!!action.error && <Alert>{action.error}</Alert>}
''',
    '''      />

      <LoadError error={job.error} onRetry={() => job.reload()} stale={job.data !== undefined} />
      <LoadError error={quote.error} onRetry={() => quote.reload()} stale={quote.data !== undefined} />
      <LoadError error={bookings.error} onRetry={() => bookings.reload()} stale={bookings.data !== undefined} />
      <LoadError error={payments.error} onRetry={() => payments.reload()} stale={payments.data !== undefined} />
      <LoadError error={completion.error} onRetry={() => completion.reload()} stale={completion.data !== undefined} />
      {!!action.error && <Alert>{action.error}</Alert>}
''',
)
# ContractorJob's stale-data branch was changed above; its existing early-error
# view remains a retry + back view when no successful job data exists.
replace_once(
    "apps/borewell-native/screens/contractor/FindRigs.js",
    'if (job.error) return <Screen><Alert>{job.error.message}</Alert></Screen>;',
    'if (job.error && !job.data) return <Screen><LoadError error={job.error} onRetry={() => job.reload()} /></Screen>;',
)
replace_once(
    "apps/borewell-native/screens/contractor/FindRigs.js",
    '''      />

      <Card style={{ padding: 0, overflow: "hidden" }}>
''',
    '''      />

      <LoadError error={job.error} onRetry={() => job.reload()} stale={job.data !== undefined} />
      <Card style={{ padding: 0, overflow: "hidden" }}>
''',
)

# Show service-area/pricing load failures without blocking the location picker.
replace_once(
    "apps/borewell-native/screens/customer/NewRequest.js",
    'Alert, Body, Button, Card, Icon, JobTypeIcon, Loading, Row, Screen, Tile, Title,',
    'Alert, Body, Button, Card, Icon, JobTypeIcon, Loading, LoadError, Row, Screen, Tile, Title,',
)
replace_once(
    "apps/borewell-native/screens/customer/NewRequest.js",
    '''      />

      <Card style={{ padding: 0, overflow: "hidden" }}>
''',
    '''      />

      <LoadError error={areas.error} onRetry={() => areas.reload()} stale={areas.data !== undefined} />
      <Card style={{ padding: 0, overflow: "hidden" }}>
''',
)
replace_once(
    "apps/borewell-native/screens/contractor/WalkIn.js",
    'Alert, Body, Button, Card, Field, Icon, Input, JobTypeIcon, Loading, Row, Screen, Tile, Title,',
    'Alert, Body, Button, Card, Field, Icon, Input, JobTypeIcon, Loading, LoadError, Row, Screen, Tile, Title,',
)
replace_once(
    "apps/borewell-native/screens/contractor/WalkIn.js",
    '''      />

      <Card>
        <Title size={19}>Customer</Title>
''',
    '''      />

      <LoadError error={areas.error} onRetry={() => areas.reload()} stale={areas.data !== undefined} />
      <Card>
        <Title size={19}>Customer</Title>
''',
)

# package test command and CI step (no added npm dependency).
package_path = ROOT / "apps/borewell-native/package.json"
package = json.loads(PLANNED_FILES.get(str(package_path.relative_to(ROOT)), package_path.read_text()))
package["scripts"]["test"] = "node --experimental-default-type=module --test services/api.test.js"
PLANNED_FILES[str(package_path.relative_to(ROOT))] = json.dumps(package, indent=2) + "\n"

replace_once(
    ".github/workflows/ci-borewell-native.yml",
    '''      - name: Install
        run: npm install

      - name: Lint
''',
    '''      - name: Install
        run: npm install

      - name: Unit tests
        run: npm test

      - name: Lint
''',
)

# Expo SDK 57 makes expo/fetch the native global by default. Keep React
# Native's built-in fetch for this release workflow so AbortController-backed
# response-body timeouts are not affected by the SDK 57 expo/fetch body-read
# regression (see the SDK-version notes in the PR description).
replace_once(
    ".github/workflows/build-demo-apk.yml",
    '''        run: |
          DOMAIN="${DOMAIN#https://}"; DOMAIN="${DOMAIN%/}"
''',
    '''        run: |
          echo "EXPO_PUBLIC_USE_RN_FETCH=1" >> "$GITHUB_ENV"
          DOMAIN="${DOMAIN#https://}"; DOMAIN="${DOMAIN%/}"
''',
)

write_changes()
print(f"Applied Phase 1 changes on branch: {git('branch', '--show-current')}")
print("Next: cd apps/borewell-native && npm test && npm run lint && npm run bundle-check")
print("No production deployment, .env.prod change, database operation, or APK build was run.")
