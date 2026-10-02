import unittest
import uuid

from data import admin_client, create_book, register_member
from shelf import (
    ShelfClient,
    assert_no_password_fields,
    expect_error,
    expect_keys,
    expect_object,
    expect_status,
    parse_date,
    utc_today,
)


class TestLoans(unittest.TestCase):
    PHASE = "A"

    def setUp(self):
        self.admin = admin_client()

    def _borrow(self, member, book):
        res = member.post("/loans", body={"bookId": book["id"]})
        expect_status(res, 201, "borrow")
        return res.body

    def test_borrow_happy_path(self):
        book = create_book(self.admin, total_copies=2, title="Happy Path")
        member, _, _ = register_member()
        res = member.post("/loans", body={"bookId": book["id"]})
        expect_status(res, 201, "borrow")
        expect_object(res, "borrow")
        loan = res.body
        expect_keys(
            loan,
            ["id", "userId", "bookId", "borrowedOn", "dueOn", "returnedOn", "fineCents", "book", "user"],
            "loan",
        )
        uuid.UUID(loan["id"])
        self.assertEqual(loan["userId"], member.user_id)
        self.assertEqual(loan["bookId"], book["id"])
        borrowed = parse_date(loan["borrowedOn"], "borrowedOn")
        due = parse_date(loan["dueOn"], "dueOn")
        self.assertLessEqual(abs((utc_today() - borrowed).days), 1, "borrowedOn is UTC today")
        self.assertEqual((due - borrowed).days, 14, "dueOn = borrowedOn + 14 days")
        self.assertEqual(loan["fineCents"], 0)
        self.assertIsNone(loan["returnedOn"])
        expect_keys(loan["book"], ["id", "title", "isbn"], "embedded book")
        expect_keys(loan["user"], ["id", "email"], "embedded user")
        self.assertEqual(loan["book"]["id"], book["id"])
        self.assertEqual(loan["user"]["id"], member.user_id)
        assert_no_password_fields(res.raw, "loan")
        detail = ShelfClient().get(f"/books/{book['id']}")
        self.assertEqual(detail.body["availableCopies"], 1)

    def test_borrow_unknown_book(self):
        member, _, _ = register_member()
        expect_error(
            member.post("/loans", body={"bookId": str(uuid.uuid4())}),
            404,
            "not_found",
            "borrow unknown book",
        )

    def test_availability_and_no_copies(self):
        book = create_book(self.admin, total_copies=2)
        m1, _, _ = register_member()
        m2, _, _ = register_member()
        m3, _, _ = register_member()
        self._borrow(m1, book)
        self.assertEqual(
            ShelfClient().get(f"/books/{book['id']}").body["availableCopies"], 1
        )
        self._borrow(m2, book)
        self.assertEqual(
            ShelfClient().get(f"/books/{book['id']}").body["availableCopies"], 0
        )
        expect_error(
            m3.post("/loans", body={"bookId": book["id"]}),
            409,
            "no_copies",
            "no copies left",
        )

    def test_loan_limit_three_per_user(self):
        member, _, _ = register_member()
        for _ in range(3):
            self._borrow(member, create_book(self.admin))
        extra = create_book(self.admin)
        expect_error(
            member.post("/loans", body={"bookId": extra["id"]}),
            409,
            "loan_limit",
            "fourth open loan",
        )
        loans = member.get("/loans?status=open").body["items"]
        expect_status(member.post(f"/loans/{loans[0]['id']}/return"), 200, "free quota")
        expect_status(
            member.post("/loans", body={"bookId": extra["id"]}),
            201,
            "borrow after returning",
        )

    def test_member_sees_only_own_loans(self):
        book = create_book(self.admin, total_copies=2)
        m1, _, _ = register_member()
        m2, _, _ = register_member()
        own = self._borrow(m1, book)
        other = self._borrow(m2, book)
        res = m1.get("/loans?status=all")
        expect_status(res, 200, "member loans")
        expect_keys(res.body, ["items", "page", "per", "total"], "loans envelope")
        ids = [loan["id"] for loan in res.body["items"]]
        self.assertIn(own["id"], ids)
        self.assertNotIn(other["id"], ids)
        for loan in res.body["items"]:
            self.assertEqual(loan["userId"], m1.user_id)
            expect_keys(loan, ["book", "user"], "loan embeds")
            expect_keys(loan["book"], ["id", "title", "isbn"], "embedded book")
            expect_keys(loan["user"], ["id", "email"], "embedded user")
        assert_no_password_fields(res.raw, "loans list")

    def test_admin_sees_all_and_filters_by_user(self):
        book = create_book(self.admin, total_copies=2)
        m1, _, _ = register_member()
        m2, _, _ = register_member()
        l1 = self._borrow(m1, book)
        l2 = self._borrow(m2, book)
        all_res = self.admin.get("/loans?status=all&per=100")
        expect_status(all_res, 200, "admin loans")
        ids = [loan["id"] for loan in all_res.body["items"]]
        self.assertIn(l1["id"], ids)
        self.assertIn(l2["id"], ids)
        filtered = self.admin.get(f"/loans?status=all&userId={m2.user_id}&per=100")
        expect_status(filtered, 200, "admin filter by userId")
        self.assertTrue(filtered.body["items"])
        for loan in filtered.body["items"]:
            self.assertEqual(loan["userId"], m2.user_id)

    def test_status_filters(self):
        member, _, _ = register_member()
        open_loan = self._borrow(member, create_book(self.admin))
        returned_loan = self._borrow(member, create_book(self.admin))
        expect_status(
            member.post(f"/loans/{returned_loan['id']}/return"), 200, "return"
        )
        opened = member.get("/loans?status=open")
        returned = member.get("/loans?status=returned")
        everything = member.get("/loans?status=all")
        for res, present, absent in (
            (opened, open_loan["id"], returned_loan["id"]),
            (returned, returned_loan["id"], open_loan["id"]),
        ):
            expect_status(res, 200, "status filter")
            ids = [loan["id"] for loan in res.body["items"]]
            self.assertIn(present, ids)
            self.assertNotIn(absent, ids)
        all_ids = [loan["id"] for loan in everything.body["items"]]
        self.assertIn(open_loan["id"], all_ids)
        self.assertIn(returned_loan["id"], all_ids)

    def test_return_by_owner_and_admin(self):
        member, _, _ = register_member()
        loan = self._borrow(member, create_book(self.admin))
        res = member.post(f"/loans/{loan['id']}/return")
        expect_status(res, 200, "owner return")
        self.assertIsNotNone(res.body["returnedOn"])
        self.assertEqual(res.body["fineCents"], 0)

        member2, _, _ = register_member()
        loan2 = self._borrow(member2, create_book(self.admin))
        admin_res = self.admin.post(f"/loans/{loan2['id']}/return")
        expect_status(admin_res, 200, "admin return")
        self.assertIsNotNone(admin_res.body["returnedOn"])

    def test_return_errors(self):
        book = create_book(self.admin, total_copies=2)
        owner, _, _ = register_member()
        intruder, _, _ = register_member()
        loan = self._borrow(owner, book)
        expect_error(
            intruder.post(f"/loans/{loan['id']}/return"),
            403,
            "forbidden",
            "return someone else's loan",
        )
        expect_status(owner.post(f"/loans/{loan['id']}/return"), 200, "first return")
        expect_error(
            owner.post(f"/loans/{loan['id']}/return"),
            409,
            "already_returned",
            "double return",
        )
        expect_error(
            owner.post(f"/loans/{uuid.uuid4()}/return"),
            404,
            "not_found",
            "unknown loan",
        )
