import unittest

from data import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    admin_client,
    create_book,
    register_member,
    unique,
)
from shelf import (
    ShelfClient,
    assert_no_password_fields,
    expect_error,
    expect_status,
    parse_date,
)
from state import load, save

BORROW_DATE = "2026-05-01"
RETURN_DATE = "2026-05-17"  # due 2026-05-15 -> 2 days -> 100 cents
OPEN_DATE = "2026-06-01"


class TestPersistenceSeed(unittest.TestCase):
    """Phase A: leave known state on disk for the restart checks."""

    PHASE = "A"

    def test_seed_state_for_restart(self):
        admin = admin_client()
        member, addr, password = register_member(name="Restart Member")

        returned_book = create_book(
            admin, total_copies=1, title=f"Restart Returned {unique('b')}"
        )
        borrow = member.post(
            "/loans",
            body={"bookId": returned_book["id"]},
            headers={"X-Test-Date": BORROW_DATE},
        )
        expect_status(borrow, 201, "seed borrow")
        returned_loan = borrow.body
        returned = member.post(
            f"/loans/{returned_loan['id']}/return",
            headers={"X-Test-Date": RETURN_DATE},
        )
        expect_status(returned, 200, "seed return")
        self.assertEqual(returned.body["fineCents"], 100)

        open_book = create_book(
            admin, total_copies=2, title=f"Restart Open {unique('b')}"
        )
        open_borrow = member.post(
            "/loans",
            body={"bookId": open_book["id"]},
            headers={"X-Test-Date": OPEN_DATE},
        )
        expect_status(open_borrow, 201, "seed open borrow")

        save(
            {
                "borrower_email": addr,
                "borrower_password": password,
                "old_token": member.token,
                "returned_book": {
                    "id": returned_book["id"],
                    "totalCopies": returned_book["totalCopies"],
                },
                "returned_loan": {
                    "id": returned_loan["id"],
                    "fineCents": 100,
                    "borrowedOn": BORROW_DATE,
                    "returnedOn": RETURN_DATE,
                },
                "open_book": {
                    "id": open_book["id"],
                    "totalCopies": open_book["totalCopies"],
                },
                "open_loan": {
                    "id": open_borrow.body["id"],
                    "borrowedOn": OPEN_DATE,
                },
            }
        )


class TestPersistenceRestart(unittest.TestCase):
    """Phase B: run after restarting with a custom PORT and JWT_SECRET."""

    PHASE = "B"

    @classmethod
    def setUpClass(cls):
        cls.state = load()
        assert cls.state, "phase A state file missing: run phase A first (SHELF_STATE)"

    def _admin(self):
        client = ShelfClient()
        res = client.post(
            "/auth/login", body={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        expect_status(res, 200, "admin login after restart")
        client.token = res.body["token"]
        return client

    def _member(self):
        client = ShelfClient()
        res = client.post(
            "/auth/login",
            body={
                "email": self.state["borrower_email"],
                "password": self.state["borrower_password"],
            },
        )
        expect_status(res, 200, "borrower login after restart")
        client.token = res.body["token"]
        return client

    def test_health_ok_on_custom_port(self):
        expect_status(ShelfClient().get("/health"), 200, "health after restart")

    def test_data_survives_restart(self):
        admin = self._admin()
        returned_book = self.state["returned_book"]
        res = admin.get(f"/books/{returned_book['id']}")
        expect_status(res, 200, "returned book persists")
        self.assertEqual(res.body["totalCopies"], returned_book["totalCopies"])
        self.assertEqual(
            res.body["availableCopies"],
            returned_book["totalCopies"],
            "returned loan freed its copy",
        )

        open_book = self.state["open_book"]
        res = admin.get(f"/books/{open_book['id']}")
        expect_status(res, 200, "open book persists")
        self.assertEqual(
            res.body["availableCopies"],
            open_book["totalCopies"] - 1,
            "open loan still occupies a copy",
        )

        users = admin.get("/users")
        expect_status(users, 200, "users persist")
        emails = [user["email"] for user in users.body]
        self.assertIn(self.state["borrower_email"], emails)

    def test_loans_and_fines_persist(self):
        member = self._member()
        res = member.get("/loans?status=all")
        expect_status(res, 200, "loans after restart")
        by_id = {loan["id"]: loan for loan in res.body["items"]}

        returned = by_id.get(self.state["returned_loan"]["id"])
        self.assertIsNotNone(returned, "returned loan persists")
        assert returned is not None
        self.assertEqual(returned["fineCents"], 100)
        self.assertEqual(
            parse_date(returned["returnedOn"], "returnedOn").isoformat(),
            self.state["returned_loan"]["returnedOn"],
        )
        self.assertEqual(
            parse_date(returned["borrowedOn"], "borrowedOn").isoformat(),
            self.state["returned_loan"]["borrowedOn"],
        )

        opened = by_id.get(self.state["open_loan"]["id"])
        self.assertIsNotNone(opened, "open loan persists")
        assert opened is not None
        self.assertIsNone(opened["returnedOn"])
        assert_no_password_fields(res.raw, "loans after restart")

    def test_old_token_rejected_after_secret_change(self):
        old = ShelfClient(token=self.state["old_token"])
        expect_error(
            old.get("/me"),
            401,
            "unauthorized",
            "token signed with the previous secret",
        )
        member = self._member()
        expect_status(member.get("/me"), 200, "fresh token accepted")

    def test_stats_include_persisted_fines(self):
        admin = self._admin()
        res = admin.get("/stats")
        expect_status(res, 200, "stats after restart")
        self.assertGreaterEqual(res.body["totalFinesCents"], 100)
