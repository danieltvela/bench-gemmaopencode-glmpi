import unittest
from datetime import date, timedelta

from data import admin_client, create_book, register_member, unique
from shelf import expect_status, parse_date, utc_today


class TestFines(unittest.TestCase):
    PHASE = "A"

    def setUp(self):
        self.admin = admin_client()

    def _make_loan(self, borrowed_on=None):
        member, _, _ = register_member()
        book = create_book(self.admin, total_copies=1, title=f"Fine {unique('f')}")
        headers = {"X-Test-Date": borrowed_on} if borrowed_on else None
        res = member.post("/loans", body={"bookId": book["id"]}, headers=headers)
        expect_status(res, 201, "borrow")
        return member, book, res.body

    def _flow(self, borrowed_on, returned_on):
        member, _, loan = self._make_loan(borrowed_on)
        expected_borrowed = date.fromisoformat(borrowed_on)
        self.assertEqual(parse_date(loan["borrowedOn"], "borrowedOn"), expected_borrowed)
        self.assertEqual(
            parse_date(loan["dueOn"], "dueOn"), expected_borrowed + timedelta(days=14)
        )
        res = member.post(
            f"/loans/{loan['id']}/return", headers={"X-Test-Date": returned_on}
        )
        expect_status(res, 200, "return")
        self.assertEqual(
            parse_date(res.body["returnedOn"], "returnedOn"),
            date.fromisoformat(returned_on),
        )
        return res.body

    def test_fine_zero_on_due_date(self):
        returned = self._flow("2026-03-01", "2026-03-15")
        self.assertEqual(returned["fineCents"], 0, "due date itself is not fined")

    def test_fine_one_day_overdue(self):
        returned = self._flow("2026-03-01", "2026-03-16")
        self.assertEqual(returned["fineCents"], 50)

    def test_fine_two_days_overdue(self):
        returned = self._flow("2026-03-01", "2026-03-17")
        self.assertEqual(returned["fineCents"], 100)

    def test_fine_fifteen_days_overdue(self):
        returned = self._flow("2026-03-01", "2026-03-30")
        self.assertEqual(returned["fineCents"], 750)

    def test_due_dates_persist(self):
        member, _, loan = self._make_loan("2026-04-10")
        listed = member.get("/loans?status=all")
        expect_status(listed, 200, "list loans")
        assert listed.body is not None
        found = next((item for item in listed.body["items"] if item["id"] == loan["id"]), None)
        self.assertIsNotNone(found, "created loan is listed")
        assert found is not None
        self.assertEqual(parse_date(found["borrowedOn"], "borrowedOn"), date(2026, 4, 10))
        self.assertEqual(parse_date(found["dueOn"], "dueOn"), date(2026, 4, 24))

    def test_no_header_uses_server_utc_today(self):
        member, _, loan = self._make_loan()
        borrowed = parse_date(loan["borrowedOn"], "borrowedOn")
        self.assertLessEqual(abs((utc_today() - borrowed).days), 1)
        self.assertEqual((parse_date(loan["dueOn"]) - borrowed).days, 14)
        res = member.post(f"/loans/{loan['id']}/return")
        expect_status(res, 200, "return without X-Test-Date")
        self.assertEqual(res.body["fineCents"], 0)
