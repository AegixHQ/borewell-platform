"""Tests for the go-live tooling. Run: python3 -m pytest tools/go-live/tests"""
# ruff: noqa: E501  (long, human-readable messages are the point of this file)
import http.server
import os
import stat
import sys
import threading
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import check_gateway_routes  # noqa: E402
import envfile  # noqa: E402
import init_env  # noqa: E402
import preflight  # noqa: E402
import smoke  # noqa: E402

ROOT = HERE.parents[2]


def good_env(**overrides):
    env = envfile.load(ROOT / ".env.prod.example")
    env.update(
        POSTGRES_PASSWORD="p" * 24, JWT_SECRET="j" * 48, GRAFANA_ADMIN_PASSWORD="g" * 16,
        PUBLIC_DOMAIN="api.borewell.in", LETSENCRYPT_EMAIL="ops@borewell.in",
        ALLOWED_ORIGINS="https://api.borewell.in",
    )
    env.update(overrides)
    return env


def errors_for(**overrides):
    return preflight.check(good_env(**overrides))[0]


# ---- init_env -------------------------------------------------------------

def test_init_creates_private_file_with_generated_secrets(tmp_path):
    (tmp_path / ".env.prod.example").write_text((ROOT / ".env.prod.example").read_text())
    assert init_env.main(["--root", str(tmp_path), "--domain", "api.borewell.in",
                          "--email", "ops@borewell.in"]) == 0
    target = tmp_path / ".env.prod"
    assert stat.S_IMODE(os.stat(target).st_mode) == 0o600
    env = envfile.load(target)
    assert env["PUBLIC_DOMAIN"] == "api.borewell.in"
    assert env["ALLOWED_ORIGINS"] == ""  # blank -> https://<PUBLIC_DOMAIN> in compose
    assert "CHANGE_ME" not in target.read_text()
    assert len({env["POSTGRES_PASSWORD"], env["JWT_SECRET"], env["GRAFANA_ADMIN_PASSWORD"]}) == 3
    # Only the user-entered section is left to fill in -> exactly these errors.
    assert preflight.check(env)[0] == []  # domain+email given, razorpay/google optional


def test_init_never_overwrites(tmp_path):
    (tmp_path / ".env.prod.example").write_text((ROOT / ".env.prod.example").read_text())
    (tmp_path / ".env.prod").write_text("KEEP=me")
    assert init_env.main(["--root", str(tmp_path)]) == 1
    assert (tmp_path / ".env.prod").read_text() == "KEEP=me"


def test_generated_secrets_are_url_safe_for_db_connection_string():
    out = init_env.build((ROOT / ".env.prod.example").read_text())
    pw = envfile.parse(out)["POSTGRES_PASSWORD"]
    assert all(c.isalnum() or c in "-_" for c in pw)


# ---- preflight ------------------------------------------------------------

def test_template_as_shipped_is_rejected():
    errs = preflight.check(envfile.load(ROOT / ".env.prod.example"))[0]
    text = " ".join(errs)
    for key in ("POSTGRES_PASSWORD", "JWT_SECRET", "PUBLIC_DOMAIN", "LETSENCRYPT_EMAIL"):
        assert key in text


def test_blank_origins_default_to_the_domain():
    assert errors_for(ALLOWED_ORIGINS="") == []


def test_good_env_passes_cash_only_with_warnings():
    errors, warnings, info = preflight.check(good_env())
    assert errors == []
    assert any("CASH-ONLY" in w for w in warnings)
    assert any("Google sign-in is OFF" in w for w in warnings)
    assert any("https://api.borewell.in/v1/payments/webhook" in i for i in info)


@pytest.mark.parametrize("domain", ["https://api.borewell.in", "api.borewell.in/", "api.borewell.in:443",
                                    "203.0.113.10", "localhost", "example.com"])
def test_bad_domains(domain):
    assert any("PUBLIC_DOMAIN" in e for e in errors_for(PUBLIC_DOMAIN=domain))


@pytest.mark.parametrize("origins", ["http://api.borewell.in", "https://api.borewell.in/",
                                     "https://localhost:5173", "https://a.in,http://b.in"])
def test_bad_origins(origins):
    assert any("ALLOWED_ORIGINS" in e for e in errors_for(ALLOWED_ORIGINS=origins))


def test_razorpay_half_configured_is_error():
    errs = errors_for(RAZORPAY_KEY_ID="rzp_test_abcdef123456")
    assert any("half-configured" in e for e in errs)


def test_razorpay_complete_test_and_live():
    full = dict(RAZORPAY_KEY_ID="rzp_test_abcdef123456", RAZORPAY_KEY_SECRET="s" * 24,
                RAZORPAY_WEBHOOK_SECRET="hooksecret123")
    errors, warnings, _ = preflight.check(good_env(**full))
    assert errors == [] and any("TEST mode" in w for w in warnings)
    full["RAZORPAY_KEY_ID"] = "rzp_live_abcdef123456"
    errors, warnings, info = preflight.check(good_env(**full))
    assert errors == [] and not any("TEST mode" in w for w in warnings)
    assert any("LIVE" in i for i in info)


def test_razorpay_bad_values():
    base = dict(RAZORPAY_KEY_SECRET="s" * 24, RAZORPAY_WEBHOOK_SECRET="hooksecret123")
    assert any("KEY_ID should look" in e for e in errors_for(RAZORPAY_KEY_ID="key_abc", **base))
    assert any("at least 8" in e for e in errors_for(
        RAZORPAY_KEY_ID="rzp_live_abcdef123456", RAZORPAY_KEY_SECRET="s" * 24, RAZORPAY_WEBHOOK_SECRET="short"))
    assert any("different value" in e for e in errors_for(
        RAZORPAY_KEY_ID="rzp_live_abcdef123456", RAZORPAY_KEY_SECRET="s" * 24, RAZORPAY_WEBHOOK_SECRET="s" * 24))


def test_google_ids():
    assert errors_for(GOOGLE_CLIENT_IDS="123456-abc.apps.googleusercontent.com") == []
    assert any("GOOGLE_CLIENT_IDS" in e for e in errors_for(GOOGLE_CLIENT_IDS="my-client-id"))


def test_admin_bootstrap_rules():
    assert any("together" in e for e in errors_for(BOOTSTRAP_ADMIN_EMAIL="a@borewell.in"))
    assert any("12 characters" in e for e in errors_for(BOOTSTRAP_ADMIN_EMAIL="a@borewell.in",
                                                       BOOTSTRAP_ADMIN_PASSWORD="short"))
    assert any("real address" in e for e in errors_for(BOOTSTRAP_ADMIN_EMAIL="admin@borewell.local",
                                                      BOOTSTRAP_ADMIN_PASSWORD="long-enough-pw-1"))
    assert errors_for(BOOTSTRAP_ADMIN_EMAIL="a@borewell.in", BOOTSTRAP_ADMIN_PASSWORD="long-enough-pw-1") == []


def test_forwarded_for_requires_closed_ports():
    assert any("X-Forwarded-For" in e for e in errors_for(
        RATE_LIMIT_TRUST_FORWARDED_FOR="1", SERVICE_BIND_ADDR="0.0.0.0"))


def test_secret_strength_and_distinctness():
    assert any("too short" in e for e in errors_for(JWT_SECRET="short"))
    assert any("dev-only" in e or "not set" in e for e in errors_for(
        JWT_SECRET="dev-only-secret-change-in-production"))
    assert any("different" in e for e in errors_for(JWT_SECRET="x" * 30 + "ab", POSTGRES_PASSWORD="x" * 30 + "ab"))


def test_loose_file_permissions_warn():
    assert any("chmod 600" in w for w in preflight.check(good_env(), 0o644)[1])
    assert not any("chmod" in w for w in preflight.check(good_env(), 0o600)[1])


def test_staging_ca_and_open_contractor_signup_warn():
    warnings = preflight.check(good_env(LETSENCRYPT_CA_SERVER="https://acme-staging-v02.api.letsencrypt.org/directory",
                                        ALLOW_PUBLIC_CONTRACTOR_REGISTRATION="1"))[1]
    assert any("STAGING" in w for w in warnings) and any("contractor" in w for w in warnings)


# ---- gateway routes -------------------------------------------------------

def test_gateway_covers_every_contract_path():
    assert check_gateway_routes.check() == []


def test_gateway_check_catches_an_unrouted_path(tmp_path):
    import shutil
    shutil.copytree(ROOT / "packages/contracts/openapi", tmp_path / "packages/contracts/openapi")
    compose = (ROOT / "docker-compose.prod.yml").read_text()
    (tmp_path / "docker-compose.prod.yml").write_text(compose.replace(" || PathPrefix(`/v1/analytics`)", ""))
    problems = check_gateway_routes.check(tmp_path)
    assert any("/v1/analytics/estimate-accuracy" in p for p in problems)


# ---- smoke test against a stand-in server ---------------------------------

def make_server(google=401, webhook=400):
    class Handler(http.server.BaseHTTPRequestHandler):
        def _send(self, code):
            self.send_response(code)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"{}")

        def do_GET(self):
            self._send(404 if self.path in ("/metrics", "/docs", "/openapi.json") else 401)

        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            self._send({"/v1/auth/login": 401, "/v1/auth/google": google,
                        "/v1/payments/webhook": webhook}.get(self.path, 404))

        def log_message(self, *a):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_port}"


def test_smoke_passes_against_healthy_server(capsys):
    server, base = make_server()
    try:
        assert smoke.run(base, expect_razorpay=True, expect_google=True, https=False) == 0
    finally:
        server.shutdown()


def test_smoke_flags_unrouted_and_unconfigured(capsys):
    server, base = make_server(google=503, webhook=502)
    try:
        assert smoke.run(base, https=False) == 0  # off is fine when not expected
        assert smoke.run(base, expect_razorpay=True, https=False) == 1
        assert smoke.run(base, expect_google=True, https=False) == 1
    finally:
        server.shutdown()


def test_smoke_fails_when_nothing_listens():
    assert smoke.run("http://127.0.0.1:9", https=False) == 1
