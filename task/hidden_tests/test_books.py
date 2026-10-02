import unittest
import uuid

from data import admin_client, book_payload, create_book, register_member, unique
from shelf import (
    ShelfClient,
    expect_error,
    expect_keys,
    expect_object,
    expect_status,
    parse_datetime,
)


class TestBooks(unittest.TestCase):
    PHASE = "A"

    def setUp(self):
        self.admin = admin_client()

    def test_admin_creates_book(self):
        payload = book_payload(
            total_copies=3, title=f"Create {unique('b')}", author="Author X"
        )
        res = self.admin.post("/books", body=payload)
        expect_status(res, 201, "create book")
        expect_object(res, "create book")
        book = res.body
        expect_keys(
            book,
            ["id", "isbn", "title", "author", "totalCopies", "availableCopies", "createdAt"],
            "created book",
        )
        uuid.UUID(book["id"])
        self.assertEqual(book["isbn"], payload["isbn"])
        self.assertEqual(book["title"], payload["title"])
        self.assertEqual(book["author"], payload["author"])
        self.assertEqual(book["totalCopies"], 3)
        self.assertEqual(book["availableCopies"], 3)
        parse_datetime(book["createdAt"], "createdAt")

    def test_only_admin_creates_books(self):
        member, _, _ = register_member()
        expect_error(
            member.post("/books", body=book_payload()),
            403,
            "forbidden",
            "member create book",
        )
        expect_error(
            ShelfClient().post("/books", body=book_payload()),
            401,
            "unauthorized",
            "anonymous create book",
        )

    def test_get_book_is_public(self):
        book = create_book(self.admin, total_copies=2)
        anon = ShelfClient()
        res = anon.get(f"/books/{book['id']}")
        expect_status(res, 200, "public book detail")
        expect_keys(
            res.body,
            ["id", "isbn", "title", "author", "totalCopies", "availableCopies", "createdAt"],
            "book detail",
        )
        self.assertEqual(res.body["availableCopies"], 2)
        expect_error(anon.get(f"/books/{uuid.uuid4()}"), 404, "not_found", "unknown book")

    def test_search_case_insensitive_and_ordered_by_title(self):
        marker = f"ord-{uuid.uuid4().hex[:8]}"
        for index in (2, 1, 3):
            create_book(
                self.admin,
                title=f"{marker}-{index}",
                author=f"Author {unique('a')}",
            )
        create_book(self.admin, title=f"extra-{marker}", author=marker)

        anon = ShelfClient()
        for query in (marker, marker.upper()):
            with self.subTest(query=query):
                res = anon.get(f"/books?query={query}&per=20")
                expect_status(res, 200, f"search {query}")
                expect_object(res, f"search {query}")
                expect_keys(res.body, ["items", "page", "per", "total"], "search envelope")
                matched = [
                    book
                    for book in res.body["items"]
                    if marker in book["title"].lower() or marker in book["author"].lower()
                ]
                self.assertEqual(len(matched), 4, f"matches for {query}")
                titles = [book["title"] for book in matched]
                self.assertEqual(titles, sorted(titles), "ordered by title asc")
                for book in matched:
                    expect_keys(book, ["availableCopies"], "search result")

    def test_pagination(self):
        marker = f"page-{uuid.uuid4().hex[:8]}"
        for index in range(3):
            create_book(self.admin, title=f"{marker}-{index}", author="Paginator")
        anon = ShelfClient()
        first = anon.get(f"/books?query={marker}&page=1&per=2")
        expect_status(first, 200, "page 1")
        self.assertEqual(first.body["page"], 1)
        self.assertEqual(first.body["per"], 2)
        self.assertEqual(first.body["total"], 3)
        self.assertEqual(len(first.body["items"]), 2)
        second = anon.get(f"/books?query={marker}&page=2&per=2")
        expect_status(second, 200, "page 2")
        self.assertEqual(second.body["total"], 3)
        self.assertEqual(len(second.body["items"]), 1)

    def test_patch_book(self):
        book = create_book(
            self.admin, total_copies=1, title=f"Patch {unique('p')}", author="Before"
        )
        res = self.admin.patch(
            f"/books/{book['id']}", body={"author": "After", "totalCopies": 4}
        )
        expect_status(res, 200, "patch book")
        self.assertEqual(res.body["author"], "After")
        self.assertEqual(res.body["totalCopies"], 4)
        self.assertEqual(res.body["availableCopies"], 4)
        fetched = ShelfClient().get(f"/books/{book['id']}")
        self.assertEqual(fetched.body["author"], "After")
        expect_error(
            self.admin.patch(f"/books/{uuid.uuid4()}", body={"author": "Nope"}),
            404,
            "not_found",
            "patch unknown book",
        )

    def test_patch_copies_cannot_drop_below_open_loans(self):
        book = create_book(self.admin, total_copies=2)
        m1, _, _ = register_member()
        m2, _, _ = register_member()
        expect_status(m1.post("/loans", body={"bookId": book["id"]}), 201, "borrow 1")
        expect_status(m2.post("/loans", body={"bookId": book["id"]}), 201, "borrow 2")
        expect_error(
            self.admin.patch(f"/books/{book['id']}", body={"totalCopies": 1}),
            409,
            "copies_below_open_loans",
            "shrink below open loans",
        )
        expect_status(
            self.admin.patch(f"/books/{book['id']}", body={"totalCopies": 2}),
            200,
            "shrink to open loans count",
        )

    def test_delete_book(self):
        book = create_book(self.admin)
        expect_status(self.admin.delete(f"/books/{book['id']}"), 204, "delete book")
        expect_error(
            ShelfClient().get(f"/books/{book['id']}"),
            404,
            "not_found",
            "deleted book",
        )

        borrowed = create_book(self.admin)
        member, _, _ = register_member()
        expect_status(member.post("/loans", body={"bookId": borrowed["id"]}), 201, "borrow")
        expect_error(
            self.admin.delete(f"/books/{borrowed['id']}"),
            409,
            "book_has_open_loans",
            "delete with open loan",
        )

    def test_create_book_validation(self):
        expect_error(
            self.admin.post("/books", body={**book_payload(), "totalCopies": 0}),
            400,
            "validation_failed",
            "zero copies",
        )
        payload = book_payload()
        payload.pop("title")
        expect_error(
            self.admin.post("/books", body=payload),
            400,
            "validation_failed",
            "missing title",
        )

    def test_member_cannot_patch_or_delete(self):
        book = create_book(self.admin)
        member, _, _ = register_member()
        expect_error(
            member.patch(f"/books/{book['id']}", body={"title": "Hacked"}),
            403,
            "forbidden",
            "member patch",
        )
        expect_error(
            member.delete(f"/books/{book['id']}"),
            403,
            "forbidden",
            "member delete",
        )
