"""HTTP client and assertions for the shelf black-box acceptance suite.

The suite never imports or inspects the application code: it only talks HTTP
to the running server.
"""

import base64
import hashlib
import hmac
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone

DEFAULT_BASE_URL = "http://127.0.0.1:8080"
REQUEST_TIMEOUT = float(os.environ.get("SHELF_HTTP_TIMEOUT", "10"))
DEFAULT_JWT_SECRET = "shelf-dev-secret"


class HttpResult:
    def __init__(self, status, body, raw, headers):
        self.status = status
        self.body = body
        self.raw = raw
        self.headers = headers


def _parse_json(raw):
    if not raw.strip():
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


class ShelfClient:
    """Minimal JSON client for one server instance."""

    def __init__(self, base_url=None, token=None):
        self.base_url = (
            base_url or os.environ.get("SHELF_BASE_URL") or DEFAULT_BASE_URL
        ).rstrip("/")
        self.token = token
        self.user_id: "str | None" = None
        self.user_email: "str | None" = None

    def request(self, method, path, body=None, token=None, headers=None):
        url = self.base_url + path
        hdrs = {"Accept": "application/json"}
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            hdrs["Content-Type"] = "application/json"
        tok = token if token is not None else self.token
        if tok:
            hdrs["Authorization"] = "Bearer " + tok
        if headers:
            hdrs.update(headers)
        req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                raw = resp.read().decode("utf-8", "replace")
                return HttpResult(resp.status, _parse_json(raw), raw, dict(resp.headers))
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", "replace")
            return HttpResult(exc.code, _parse_json(raw), raw, dict(exc.headers))

    def get(self, path, **kw):
        return self.request("GET", path, **kw)

    def post(self, path, **kw):
        return self.request("POST", path, **kw)

    def patch(self, path, **kw):
        return self.request("PATCH", path, **kw)

    def delete(self, path, **kw):
        return self.request("DELETE", path, **kw)


def expect_status(res, status, context=""):
    ctx = f"{context}: " if context else ""
    assert res.status == status, (
        f"{ctx}expected HTTP {status}, got {res.status}: {res.raw[:500]}"
    )
    return res


def expect_json(res, context=""):
    ctx = f"{context}: " if context else ""
    assert res.body is not None, f"{ctx}expected JSON body, got: {res.raw[:500]!r}"
    return res


def expect_object(res, context=""):
    expect_json(res, context)
    ctx = f"{context}: " if context else ""
    assert isinstance(res.body, dict), (
        f"{ctx}expected JSON object, got {type(res.body).__name__}: {res.raw[:500]}"
    )
    return res


def expect_error(res, status, code, context=""):
    expect_status(res, status, context)
    expect_object(res, context)
    ctx = f"{context}: " if context else ""
    error = res.body.get("error")
    assert isinstance(error, str) and error.strip(), (
        f"{ctx}error field missing or empty: {res.raw[:500]}"
    )
    got = res.body.get("code")
    assert got == code, (
        f"{ctx}expected code {code!r}, got {got!r}: {res.raw[:500]}"
    )
    return res


def expect_keys(obj, keys, context=""):
    ctx = f"{context}: " if context else ""
    missing = [key for key in keys if key not in obj]
    assert not missing, f"{ctx}missing keys {missing} (have {sorted(obj)})"


def assert_no_password_fields(raw, context=""):
    ctx = f"{context}: " if context else ""
    for marker in ('"passwordHash"', '"password_hash"', '"password"'):
        assert marker not in raw, f"{ctx}response leaked {marker}: {raw[:300]}"


def parse_datetime(value, context=""):
    ctx = f"{context}: " if context else ""
    assert isinstance(value, str), f"{ctx}expected ISO-8601 string, got {value!r}"
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise AssertionError(f"{ctx}invalid ISO-8601 date {value!r}") from exc
    assert parsed.tzinfo is not None, f"{ctx}date {value!r} has no timezone offset"
    return parsed


def parse_date(value, context=""):
    return parse_datetime(value, context).astimezone(timezone.utc).date()


def utc_today():
    return datetime.now(timezone.utc).date()


def _b64url(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(segment):
    pad = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + pad)


def jwt_decode(token):
    parts = token.split(".")
    assert len(parts) == 3, f"not a JWT: {token[:60]!r}"
    header = json.loads(_b64url_decode(parts[0]))
    payload = json.loads(_b64url_decode(parts[1]))
    return header, payload


def forge_hs256(payload, secret, header=None):
    if header is None:
        header = {"alg": "HS256", "typ": "JWT"}
    head = _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    body = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{head}.{body}".encode("ascii")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{head}.{body}.{_b64url(signature)}"
