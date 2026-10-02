import unittest

from data import ADMIN_EMAIL, admin_client, create_book, register_member
from shelf import (
    assert_no_password_fields,
    expect_error,
    expect_json,
    expect_keys,
    expect_object,
    expect_status,
)


class TestUsersAndStats(unittest.TestCase):
    PHASE = "A"

    def setUp(self):
        self.admin = admin_client()

    def test_users_list_admin_only(self):
        member, addr, _ = register_member(name="Listed Member")
        expect_error(member.get("/users"), 403, "forbidden", "member lists users")
        res = self.admin.get("/users")
        expect_status(res, 200, "admin lists users")
        expect_json(res, "users")
        self.assertIsInstance(res.body, list)
        for user in res.body:
            expect_keys(user, ["id", "email", "name", "role"], "public user")
        emails = [user["email"] for user in res.body]
        self.assertEqual(emails, sorted(emails), "users ordered by email")
        self.assertIn(addr, emails)
        self.assertIn(ADMIN_EMAIL, emails)
        assert_no_password_fields(res.raw, "users list")

    def test_me_returns_public_user(self):
        member, addr, _ = register_member(name="Me User")
        res = member.get("/me")
        expect_status(res, 200, "/me")
        expect_keys(res.body, ["id", "email", "name", "role"], "/me")
        self.assertEqual(res.body["email"], addr)
        self.assertEqual(res.body["role"], "member")
        assert_no_password_fields(res.raw, "/me")

    def test_stats_permissions_and_shape(self):
        member, _, _ = register_member()
        expect_error(member.get("/stats"), 403, "forbidden", "member stats")
        res = self.admin.get("/stats")
        expect_status(res, 200, "admin stats")
        expect_object(res, "stats")
        for key in ("users", "books", "openLoans", "totalFinesCents"):
            self.assertIn(key, res.body, f"stats key {key}")
            self.assertIsInstance(res.body[key], int, f"stats {key} is int")
            self.assertGreaterEqual(res.body[key], 0)

    def test_stats_deltas_track_activity(self):
        before = self.admin.get("/stats").body
        member, _, _ = register_member()
        book = create_book(self.admin)
        borrow = member.post(
            "/loans",
            body={"bookId": book["id"]},
            headers={"X-Test-Date": "2026-02-01"},
        )
        expect_status(borrow, 201, "borrow")
        mid = self.admin.get("/stats").body
        self.assertEqual(mid["users"], before["users"] + 1)
        self.assertEqual(mid["books"], before["books"] + 1)
        self.assertEqual(mid["openLoans"], before["openLoans"] + 1)
        self.assertEqual(mid["totalFinesCents"], before["totalFinesCents"])

        returned = member.post(
            f"/loans/{borrow.body['id']}/return",
            headers={"X-Test-Date": "2026-02-18"},
        )
        expect_status(returned, 200, "return overdue")
        self.assertEqual(returned.body["fineCents"], 150, "3 days overdue")
        after = self.admin.get("/stats").body
        self.assertEqual(after["openLoans"], mid["openLoans"] - 1)
        self.assertEqual(after["totalFinesCents"], before["totalFinesCents"] + 150)
