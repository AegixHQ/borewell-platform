/**
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
