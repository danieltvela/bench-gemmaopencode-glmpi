import Fluent
import Vapor

private struct RegisterBody: Content {
    var email: String
    var password: String
    var name: String
}

private struct LoginBody: Content {
    var email: String
    var password: String
}

private struct CreateBookBody: Content {
    var isbn: String
    var title: String
    var author: String
    var totalCopies: Int
}

private struct PatchBookBody: Content {
    var isbn: String?
    var title: String?
    var author: String?
    var totalCopies: Int?
}

private struct BorrowBody: Content {
    var bookId: UUID
}

func routes(_ app: Application) throws {
    app.get("health") { _ async -> HealthResponse in
        HealthResponse(status: "ok")
    }

    app.post("auth", "register", use: register)
    app.post("auth", "login", use: login)
    app.get("me", use: me)

    app.get("books", use: listBooks)
    app.get("books", ":bookID", use: getBook)
    app.post("books", use: createBook)
    app.patch("books", ":bookID", use: patchBook)
    app.delete("books", ":bookID", use: deleteBook)

    app.post("loans", use: borrow)
    app.get("loans", use: listLoans)
    app.post("loans", ":loanID", "return", use: returnLoan)

    app.get("users", use: listUsers)
    app.get("stats", use: stats)
}

// MARK: - Auth

private func register(_ request: Request) async throws -> Response {
    let body = try request.content.decode(RegisterBody.self)
    let email = body.email.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
    let name = body.name.trimmingCharacters(in: .whitespacesAndNewlines)
    guard email.contains("@"), !name.isEmpty, body.password.count >= 8 else {
        throw AppError.validationFailed
    }
    if try await User.query(on: request.db).filter(\.$email == email).first() != nil {
        throw AppError.emailTaken
    }
    let user = User(
        email: email,
        passwordHash: try Bcrypt.hash(body.password),
        name: name,
        role: "member"
    )
    try await user.save(on: request.db)
    let payload = AuthResponse(
        id: try user.requireID(),
        email: user.email,
        name: user.name,
        role: user.role,
        token: try Auth.token(for: user, app: request.application)
    )
    return try await payload.encodeResponse(status: .created, for: request)
}

private func login(_ request: Request) async throws -> AuthResponse {
    let body = try request.content.decode(LoginBody.self)
    let email = body.email.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
    guard
        let user = try await User.query(on: request.db).filter(\.$email == email).first(),
        (try? Bcrypt.verify(body.password, created: user.passwordHash)) == true
    else {
        throw AppError.unauthorized
    }
    return AuthResponse(
        id: try user.requireID(),
        email: user.email,
        name: user.name,
        role: user.role,
        token: try Auth.token(for: user, app: request.application)
    )
}

private func me(_ request: Request) async throws -> PublicUser {
    try await Auth.requireUser(request).publicDTO
}

// MARK: - Books

private func listBooks(_ request: Request) async throws -> BookListResponse {
    let page = max(request.query[Int.self, at: "page"] ?? 1, 1)
    let per = min(max(request.query[Int.self, at: "per"] ?? 20, 1), 100)
    let search = request.query[String.self, at: "query"]
    let query = Book.query(on: request.db)
    if let search, !search.isEmpty {
        query.group(.or) { group in
            group.filter(\.$title ~~ search)
            group.filter(\.$author ~~ search)
        }
    }
    let total = try await query.count()
    let books = try await query
        .sort(\.$title, .ascending)
        .range((page - 1) * per ..< page * per)
        .all()
    var items: [BookResponse] = []
    for book in books {
        items.append(try await book.response(on: request.db))
    }
    return BookListResponse(items: items, page: page, per: per, total: total)
}

private func getBook(_ request: Request) async throws -> BookResponse {
    guard let id = request.parameters.get("bookID", as: UUID.self) else {
        throw AppError.notFound
    }
    guard let book = try await Book.find(id, on: request.db) else {
        throw AppError.notFound
    }
    return try await book.response(on: request.db)
}

private func createBook(_ request: Request) async throws -> Response {
    _ = try await Auth.requireUser(request, role: "admin")
    let body = try request.content.decode(CreateBookBody.self)
    let isbn = body.isbn.trimmingCharacters(in: .whitespacesAndNewlines)
    let title = body.title.trimmingCharacters(in: .whitespacesAndNewlines)
    let author = body.author.trimmingCharacters(in: .whitespacesAndNewlines)
    guard !isbn.isEmpty, !title.isEmpty, !author.isEmpty, body.totalCopies >= 1 else {
        throw AppError.validationFailed
    }
    if try await Book.query(on: request.db).filter(\.$isbn == isbn).first() != nil {
        throw AppError.isbnTaken
    }
    let book = Book(isbn: isbn, title: title, author: author, totalCopies: body.totalCopies)
    try await book.save(on: request.db)
    return try await book.response(on: request.db)
        .encodeResponse(status: .created, for: request)
}

private func patchBook(_ request: Request) async throws -> BookResponse {
    _ = try await Auth.requireUser(request, role: "admin")
    guard
        let id = request.parameters.get("bookID", as: UUID.self),
        let book = try await Book.find(id, on: request.db)
    else {
        throw AppError.notFound
    }
    let body = try request.content.decode(PatchBookBody.self)
    if let raw = body.isbn {
        let isbn = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !isbn.isEmpty else { throw AppError.validationFailed }
        if isbn != book.isbn,
           try await Book.query(on: request.db).filter(\.$isbn == isbn).first() != nil {
            throw AppError.isbnTaken
        }
        book.isbn = isbn
    }
    if let raw = body.title {
        let title = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !title.isEmpty else { throw AppError.validationFailed }
        book.title = title
    }
    if let raw = body.author {
        let author = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !author.isEmpty else { throw AppError.validationFailed }
        book.author = author
    }
    if let copies = body.totalCopies {
        guard copies >= 1 else { throw AppError.validationFailed }
        let open = try await LoanService.openLoanCount(for: book, on: request.db)
        guard copies >= open else { throw AppError.copiesBelowOpenLoans }
        book.totalCopies = copies
    }
    try await book.save(on: request.db)
    return try await book.response(on: request.db)
}

private func deleteBook(_ request: Request) async throws -> HTTPStatus {
    _ = try await Auth.requireUser(request, role: "admin")
    guard
        let id = request.parameters.get("bookID", as: UUID.self),
        let book = try await Book.find(id, on: request.db)
    else {
        throw AppError.notFound
    }
    guard try await LoanService.openLoanCount(for: book, on: request.db) == 0 else {
        throw AppError.bookHasOpenLoans
    }
    try await book.delete(on: request.db)
    return .noContent
}

// MARK: - Loans

private func borrow(_ request: Request) async throws -> Response {
    let user = try await Auth.requireUser(request)
    let body = try request.content.decode(BorrowBody.self)
    guard let book = try await Book.find(body.bookId, on: request.db) else {
        throw AppError.notFound
    }
    let loan = try await LoanService.borrow(
        user: user,
        book: book,
        today: Clock.today(request),
        on: request.db
    )
    return try await loan.response(on: request.db)
        .encodeResponse(status: .created, for: request)
}

private func listLoans(_ request: Request) async throws -> LoanListResponse {
    let user = try await Auth.requireUser(request)
    let status = request.query[String.self, at: "status"] ?? "all"
    let page = max(request.query[Int.self, at: "page"] ?? 1, 1)
    let per = min(max(request.query[Int.self, at: "per"] ?? 20, 1), 100)
    let query = Loan.query(on: request.db)
    if user.role == "admin" {
        if let userID = request.query[UUID.self, at: "userId"] {
            query.filter(\.$user.$id == userID)
        }
    } else {
        query.filter(\.$user.$id == (try user.requireID()))
    }
    switch status {
    case "open":
        query.filter(\.$returnedOn == nil)
    case "returned":
        query.filter(\.$returnedOn != nil)
    default:
        break
    }
    let total = try await query.count()
    let loans = try await query
        .sort(\.$borrowedOn, .descending)
        .range((page - 1) * per ..< page * per)
        .all()
    var items: [LoanResponse] = []
    for loan in loans {
        items.append(try await loan.response(on: request.db))
    }
    return LoanListResponse(items: items, page: page, per: per, total: total)
}

private func returnLoan(_ request: Request) async throws -> LoanResponse {
    let user = try await Auth.requireUser(request)
    guard let id = request.parameters.get("loanID", as: UUID.self) else {
        throw AppError.notFound
    }
    guard
        let loan = try await Loan.query(on: request.db)
            .filter(\.$id == id)
            .with(\.$book)
            .with(\.$user)
            .first()
    else {
        throw AppError.notFound
    }
    if user.role != "admin", try loan.$user.id != user.requireID() {
        throw AppError.forbidden
    }
    _ = try await LoanService.returnLoan(loan, today: Clock.today(request), on: request.db)
    return try await loan.response(on: request.db)
}

// MARK: - Admin

private func listUsers(_ request: Request) async throws -> [PublicUser] {
    _ = try await Auth.requireUser(request, role: "admin")
    let users = try await User.query(on: request.db).sort(\.$email, .ascending).all()
    return try users.map { try $0.publicDTO }
}

private func stats(_ request: Request) async throws -> StatsResponse {
    _ = try await Auth.requireUser(request, role: "admin")
    let users = try await User.query(on: request.db).count()
    let books = try await Book.query(on: request.db).count()
    let openLoans = try await Loan.query(on: request.db).filter(\.$returnedOn == nil).count()
    let fines = try await Loan.query(on: request.db).sum(\.$fineCents) ?? 0
    return StatsResponse(
        users: users,
        books: books,
        openLoans: openLoans,
        totalFinesCents: fines
    )
}
