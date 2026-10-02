"""Unique test data factories and common flows for the shelf suite."""

import uuid

from shelf import ShelfClient, expect_status

ADMIN_EMAIL = "admin@shelf.test"
ADMIN_PASSWORD = "admin-pass"

_admin_tokens = {}


def unique(prefix="x"):
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def email(prefix="user"):
    return f"{unique(prefix)}@shelf-test.example"


def isbn():
    return str(uuid.uuid4().int % 10**13).zfill(13)


def book_payload(total_copies=1, title=None, author=None, isbn_value=None):
    return {
        "isbn": isbn_value or isbn(),
        "title": title if title is not None else f"Book {unique('title')}",
        "author": author if author is not None else f"Author {unique('author')}",
        "totalCopies": total_copies,
    }


def admin_client(base_url=None):
    key = base_url or ""
    if key not in _admin_tokens:
        client = ShelfClient(base_url)
        res = client.post(
            "/auth/login", body={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        expect_status(res, 200, "seed admin login")
        _admin_tokens[key] = res.body["token"]
    return ShelfClient(base_url, token=_admin_tokens[key])


def create_book(admin, total_copies=1, title=None, author=None):
    res = admin.post("/books", body=book_payload(total_copies, title, author))
    expect_status(res, 201, "admin create book")
    return res.body


def register_member(base_url=None, password=None, name=None):
    client = ShelfClient(base_url)
    addr = email()
    pw = password or ("member-pass-" + uuid.uuid4().hex[:10])
    res = client.post(
        "/auth/register",
        body={"email": addr, "password": pw, "name": name or "Test Member"},
    )
    expect_status(res, 201, "member register")
    client.token = res.body["token"]
    client.user_id = res.body["id"]
    client.user_email = addr
    return client, addr, pw
