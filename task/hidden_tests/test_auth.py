import unittest
import uuid

from data import ADMIN_EMAIL, ADMIN_PASSWORD, email
from shelf import (
    ShelfClient,
    assert_no_password_fields,
    expect_error,
    expect_keys,
    expect_object,
    expect_status,
)


class TestAuth(unittest.TestCase):
    PHASE = "A"

    def test_register_returns_member_with_working_token(self):
        client = ShelfClient()
        addr = email()
        res = client.post(
            "/auth/register",
            body={"email": addr, "password": "secret-pass-1", "name": "Alice"},
        )
        expect_status(res, 201, "register")
        expect_object(res, "register")
        body = res.body
        expect_keys(body, ["id", "email", "name", "role", "token"], "register")
        uuid.UUID(body["id"])
        self.assertEqual(body["email"], addr)
        self.assertEqual(body["name"], "Alice")
        self.assertEqual(body["role"], "member")
        self.assertNotIn("password", body)

        me = client.get("/me", token=body["token"])
        expect_status(me, 200, "/me with fresh token")
        self.assertEqual(me.body["id"], body["id"])
        self.assertEqual(me.body["email"], addr)
        self.assertEqual(me.body["role"], "member")
        assert_no_password_fields(me.raw, "/me")

    def test_register_normalizes_email_to_lowercase(self):
        client = ShelfClient()
        mixed = f"Case-{uuid.uuid4().hex[:8]}@Shelf-Test.Example"
        res = client.post(
            "/auth/register",
            body={"email": mixed, "password": "secret-pass-1", "name": "Case"},
        )
        expect_status(res, 201, "register mixed case")
        expected = mixed.lower()
        self.assertEqual(res.body["email"], expected)

        login = client.post(
            "/auth/login", body={"email": expected, "password": "secret-pass-1"}
        )
        expect_status(login, 200, "login with lowercase email")

        duplicate = client.post(
            "/auth/register",
            body={"email": mixed.upper(), "password": "secret-pass-1", "name": "Case"},
        )
        expect_error(duplicate, 409, "email_taken", "duplicate with different case")

    def test_register_rejects_invalid_payload(self):
        client = ShelfClient()
        cases = [
            ("7-char password", {"email": email(), "password": "short7c", "name": "X"}),
            ("missing name", {"email": email(), "password": "secret-pass-1"}),
            ("missing email", {"password": "secret-pass-1", "name": "X"}),
        ]
        for label, body in cases:
            with self.subTest(label=label):
                expect_error(
                    client.post("/auth/register", body=body),
                    400,
                    "validation_failed",
                    label,
                )

    def test_login_rejects_bad_credentials(self):
        client = ShelfClient()
        addr = email()
        client.post(
            "/auth/register",
            body={"email": addr, "password": "secret-pass-1", "name": "Bob"},
        )
        expect_error(
            client.post("/auth/login", body={"email": addr, "password": "wrong-pass-1"}),
            401,
            "unauthorized",
            "wrong password",
        )
        expect_error(
            client.post(
                "/auth/login", body={"email": email(), "password": "secret-pass-1"}
            ),
            401,
            "unauthorized",
            "unknown email",
        )

    def test_login_returns_public_user_and_token(self):
        client = ShelfClient()
        addr = email()
        registered = client.post(
            "/auth/register",
            body={"email": addr, "password": "secret-pass-1", "name": "Carol"},
        )
        expect_status(registered, 201, "register")
        login = client.post(
            "/auth/login", body={"email": addr, "password": "secret-pass-1"}
        )
        expect_status(login, 200, "login")
        expect_keys(login.body, ["id", "email", "name", "role", "token"], "login")
        self.assertEqual(login.body["id"], registered.body["id"])
        self.assertEqual(login.body["role"], "member")

    def test_seed_admin_can_log_in(self):
        client = ShelfClient()
        res = client.post(
            "/auth/login", body={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        expect_status(res, 200, "seed admin login")
        self.assertEqual(res.body["email"], ADMIN_EMAIL)
        self.assertEqual(res.body["role"], "admin")

    def test_register_does_not_escalate_role(self):
        client = ShelfClient()
        res = client.post(
            "/auth/register",
            body={
                "email": email(),
                "password": "secret-pass-1",
                "name": "Mallory",
                "role": "admin",
            },
        )
        if res.status == 201:
            self.assertEqual(res.body["role"], "member")
        else:
            expect_error(res, 400, "validation_failed", "role injection rejected")
