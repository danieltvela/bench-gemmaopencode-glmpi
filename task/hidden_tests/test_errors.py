import unittest
import uuid

from data import admin_client, book_payload, create_book, email, register_member
from shelf import ShelfClient, expect_error, expect_status


class TestErrorContract(unittest.TestCase):
    PHASE = "A"

    def setUp(self):
        self.admin = admin_client()

    def test_basic_error_codes(self):
        anon = ShelfClient()
        with self.subTest(code="unauthorized"):
            expect_error(anon.get("/me"), 401, "unauthorized")
        member, addr, _ = register_member()
        with self.subTest(code="forbidden"):
            expect_error(member.post("/books", body=book_payload()), 403, "forbidden")
        with self.subTest(code="not_found"):
            expect_error(anon.get(f"/books/{uuid.uuid4()}"), 404, "not_found")
        with self.subTest(code="validation_failed"):
            expect_error(
                anon.post(
                    "/auth/register",
                    body={"email": email(), "password": "short", "name": "X"},
                ),
                400,
                "validation_failed",
            )
        with self.subTest(code="email_taken"):
            expect_error(
                anon.post(
                    "/auth/register",
                    body={"email": addr, "password": "secret-pass-1", "name": "Dup"},
                ),
                409,
                "email_taken",
            )

    def test_business_error_codes(self):
        with self.subTest(code="no_copies"):
            book = create_book(self.admin, total_copies=1)
            first, _, _ = register_member()
            second, _, _ = register_member()
            expect_status(first.post("/loans", body={"bookId": book["id"]}), 201)
            expect_error(
                second.post("/loans", body={"bookId": book["id"]}), 409, "no_copies"
            )
        with self.subTest(code="loan_limit"):
            limited, _, _ = register_member()
            for _ in range(3):
                expect_status(
                    limited.post("/loans", body={"bookId": create_book(self.admin)["id"]}),
                    201,
                )
            expect_error(
                limited.post(
                    "/loans", body={"bookId": create_book(self.admin)["id"]}
                ),
                409,
                "loan_limit",
            )
        with self.subTest(code="already_returned"):
            member, _, _ = register_member()
            book = create_book(self.admin)
            loan = member.post("/loans", body={"bookId": book["id"]}).body
            expect_status(member.post(f"/loans/{loan['id']}/return"), 200)
            expect_error(
                member.post(f"/loans/{loan['id']}/return"), 409, "already_returned"
            )
        with self.subTest(code="book_has_open_loans"):
            book = create_book(self.admin)
            member, _, _ = register_member()
            expect_status(member.post("/loans", body={"bookId": book["id"]}), 201)
            expect_error(
                self.admin.delete(f"/books/{book['id']}"), 409, "book_has_open_loans"
            )
        with self.subTest(code="copies_below_open_loans"):
            book = create_book(self.admin, total_copies=2)
            m1, _, _ = register_member()
            m2, _, _ = register_member()
            expect_status(m1.post("/loans", body={"bookId": book["id"]}), 201)
            expect_status(m2.post("/loans", body={"bookId": book["id"]}), 201)
            expect_error(
                self.admin.patch(f"/books/{book['id']}", body={"totalCopies": 1}),
                409,
                "copies_below_open_loans",
            )
