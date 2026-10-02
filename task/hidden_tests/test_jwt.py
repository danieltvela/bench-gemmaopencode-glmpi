import time
import unittest

from data import email
from shelf import (
    DEFAULT_JWT_SECRET,
    ShelfClient,
    expect_error,
    expect_status,
    forge_hs256,
    jwt_decode,
)


class TestJWT(unittest.TestCase):
    PHASE = "A"

    def _register(self, client):
        res = client.post(
            "/auth/register",
            body={"email": email(), "password": "secret-pass-1", "name": "Jwt User"},
        )
        expect_status(res, 201, "register")
        return res.body

    def test_token_claims(self):
        client = ShelfClient()
        user = self._register(client)
        header, payload = jwt_decode(user["token"])
        self.assertEqual(header.get("alg"), "HS256")
        self.assertEqual(payload.get("sub"), user["id"])
        now = int(time.time())
        self.assertIn("exp", payload)
        issued = payload.get("iat", now)
        self.assertAlmostEqual(payload["exp"] - issued, 3600, delta=60)
        self.assertGreater(payload["exp"], now - 5)
        expect_status(client.get("/me", token=user["token"]), 200, "/me with token")

    def test_default_secret_is_documented_value(self):
        client = ShelfClient()
        user = self._register(client)
        now = int(time.time())
        forged = forge_hs256(
            {"sub": user["id"], "iat": now, "exp": now + 3600}, DEFAULT_JWT_SECRET
        )
        res = client.get("/me", token=forged)
        expect_status(res, 200, "token signed with documented default secret")
        self.assertEqual(res.body["id"], user["id"])

    def test_rejects_token_signed_with_wrong_secret(self):
        client = ShelfClient()
        user = self._register(client)
        now = int(time.time())
        forged = forge_hs256(
            {"sub": user["id"], "iat": now, "exp": now + 3600}, "not-the-secret"
        )
        expect_error(client.get("/me", token=forged), 401, "unauthorized", "wrong secret")

    def test_rejects_expired_token(self):
        client = ShelfClient()
        user = self._register(client)
        now = int(time.time())
        forged = forge_hs256(
            {"sub": user["id"], "iat": now - 7200, "exp": now - 3600},
            DEFAULT_JWT_SECRET,
        )
        expect_error(client.get("/me", token=forged), 401, "unauthorized", "expired token")

    def test_rejects_missing_or_malformed_token(self):
        client = ShelfClient()
        expect_error(client.get("/me"), 401, "unauthorized", "no token")
        expect_error(client.get("/me", token="garbage"), 401, "unauthorized", "garbage token")
        expect_error(
            client.get("/me", headers={"Authorization": "Basic abc"}),
            401,
            "unauthorized",
            "basic auth scheme",
        )
