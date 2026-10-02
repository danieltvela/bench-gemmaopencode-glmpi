Build a REST API in Swift with Vapor 4, runnable on Linux, named "shelf".

Goal: a library lending service complete enough to require models, relations, auth, business rules, and persistence, but scoped to a single binary and SQLite. Do not add a frontend, queues, microservices, or Postgres.

Required stack
- Swift 5.9+ / SPM. Packages: vapor, fluent, fluent-sqlite-driver, jwt (vapor/jwt).
- Database: SQLite in the file ./shelf.sqlite (create it if it does not exist). Run migrations automatically on startup.
- Port: environment variable PORT, default 8080. Host 0.0.0.0.
- JWT HS256. Secret: environment variable JWT_SECRET, default "shelf-dev-secret". Access token expires in 3600 seconds. Claim "sub" = user id (UUID string).
- Dates in JSON: ISO-8601 with timezone (date-time). Money and fines in integer cents.
- "Today" for due-date rules is the server's UTC date, unless the header X-Test-Date: YYYY-MM-DD is present: in that case use it as the current date only for computing due dates and fines. Do not persist it.

Startup
- A single command must leave the server listening: `swift run App serve --hostname 0.0.0.0 --port $PORT` (or the equivalent target from the template).
- On startup, if the users table is empty, insert exactly this admin:
  email: admin@shelf.test
  password: admin-pass
  name: Admin
  role: admin
- Include a short README with the start command and environment variables. Include a multi-stage Dockerfile that builds and runs on Linux (official Swift image) and exposes 8080. Publishing the image is not required.

Model
User: id UUID, email unique case-insensitive, passwordHash, name, role ("member" | "admin"), createdAt.
Book: id UUID, isbn unique, title, author, totalCopies Int >= 1, createdAt.
Loan: id UUID, userId, bookId, borrowedOn (date), dueOn (date), returnedOn (optional date), fineCents Int (0 until return).
A borrowed, unreturned copy occupies one copy. availableCopies = totalCopies - open loans for that book.

Rules
- Only an admin creates/updates/deletes books and lists all users.
- A member can only see and manage their own loans. An admin sees all loans.
- Maximum of 3 open loans per user.
- A book cannot be loaned when availableCopies == 0.
- dueOn = borrowedOn + 14 days.
- Return: returnedOn = current date. If current date > dueOn, fineCents = 50 * days overdue (the due date itself is not fined; the next day counts as 1). Otherwise fineCents = 0.
- An already returned loan cannot be returned again.
- A book with open loans cannot be deleted (409).
- Emails normalized to lowercase. Password minimum 8 characters.

Auth
- POST /auth/register  body {email, password, name} → 201 {id, email, name, role:"member", token}
  409 if the email exists. 400 if validation fails.
- POST /auth/login     body {email, password} → 200 {id, email, name, role, token}
  401 if credentials are invalid.
- Protected routes: header Authorization: Bearer <token>. 401 if missing or invalid.

Endpoints (JSON; errors { "error": string, "code": string })
- GET    /health                         → 200 { "status": "ok" } with no auth.
- GET    /me                             → authenticated user, no password.
- POST   /books                          admin. body {isbn, title, author, totalCopies} → 201 Book.
- GET    /books?query=&page=1&per=20     public. query searches title or author (contains, case-insensitive). Order by title asc. Response {items:[Book+availableCopies], page, per, total}.
- GET    /books/:id                      public. 404 if it does not exist. Includes availableCopies.
- PATCH  /books/:id                      admin. optional fields isbn, title, author, totalCopies. totalCopies cannot drop below open loans (409).
- DELETE /books/:id                      admin. 204. 409 if there are open loans.
- POST   /loans                          body {bookId}. 201 Loan with borrowedOn=today, dueOn, fineCents=0, returnedOn=null. 409 if user quota exceeded or no copies. 404 if book does not exist.
- GET    /loans?status=open|returned|all page, per. member: only their own. admin: all, optional userId filter. Include book {id,title,isbn} and user {id,email}.
- POST   /loans/:id/return               owner or admin. 200 Loan updated with returnedOn and fineCents. 409 if already returned. 403 if a member tries someone else's loan.
- GET    /users                          admin. list {id,email,name,role} with no pagination, ordered by email.
- GET    /stats                          admin. {users, books, openLoans, totalFinesCents}.

Stable error codes in "code": validation_failed, unauthorized, forbidden, not_found, email_taken, no_copies, loan_limit, already_returned, book_has_open_loans, copies_below_open_loans.

Object shapes
Book: {id, isbn, title, author, totalCopies, availableCopies, createdAt}
Loan: {id, userId, bookId, borrowedOn, dueOn, returnedOn, fineCents, book, user}
Public user: {id, email, name, role}

Implementation constraints
- Loan, fine, and quota logic lives in a testable service, not only in the controller.
- UUIDs are generated by the server.
- No debug routes. Do not use Leaf.
- The process must survive restarts: state lives in SQLite.
- After `swift build` on Linux the binary must start and satisfy the contract above with no manual steps beyond environment variables.

Done when
GET /health returns ok, the seed admin can log in, and a flow of register → create book as admin → borrow as member → return with X-Test-Date after the due date produces the exact fine of 50 cents per day.
