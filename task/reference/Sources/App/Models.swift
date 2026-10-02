import Fluent
import Vapor

final class User: Model, @unchecked Sendable {
    static let schema = "users"

    @ID(key: .id) var id: UUID?
    @Field(key: "email") var email: String
    @Field(key: "password_hash") var passwordHash: String
    @Field(key: "name") var name: String
    @Field(key: "role") var role: String
    @Timestamp(key: "created_at", on: .create) var createdAt: Date?

    init() {}

    init(id: UUID? = nil, email: String, passwordHash: String, name: String, role: String) {
        self.id = id
        self.email = email
        self.passwordHash = passwordHash
        self.name = name
        self.role = role
    }

    var publicDTO: PublicUser {
        get throws {
            PublicUser(id: try requireID(), email: email, name: name, role: role)
        }
    }
}

final class Book: Model, @unchecked Sendable {
    static let schema = "books"

    @ID(key: .id) var id: UUID?
    @Field(key: "isbn") var isbn: String
    @Field(key: "title") var title: String
    @Field(key: "author") var author: String
    @Field(key: "total_copies") var totalCopies: Int
    @Timestamp(key: "created_at", on: .create) var createdAt: Date?

    init() {}

    init(id: UUID? = nil, isbn: String, title: String, author: String, totalCopies: Int) {
        self.id = id
        self.isbn = isbn
        self.title = title
        self.author = author
        self.totalCopies = totalCopies
    }

    func response(on db: Database) async throws -> BookResponse {
        BookResponse(
            id: try requireID(),
            isbn: isbn,
            title: title,
            author: author,
            totalCopies: totalCopies,
            availableCopies: try await LoanService.availableCopies(for: self, on: db),
            createdAt: createdAt ?? Date()
        )
    }
}

final class Loan: Model, @unchecked Sendable {
    static let schema = "loans"

    @ID(key: .id) var id: UUID?
    @Parent(key: "user_id") var user: User
    @Parent(key: "book_id") var book: Book
    @Field(key: "borrowed_on") var borrowedOn: Date
    @Field(key: "due_on") var dueOn: Date
    @OptionalField(key: "returned_on") var returnedOn: Date?
    @Field(key: "fine_cents") var fineCents: Int

    init() {}

    init(
        id: UUID? = nil,
        userID: UUID,
        bookID: UUID,
        borrowedOn: Date,
        dueOn: Date,
        returnedOn: Date?,
        fineCents: Int
    ) {
        self.id = id
        self.$user.id = userID
        self.$book.id = bookID
        self.borrowedOn = borrowedOn
        self.dueOn = dueOn
        self.returnedOn = returnedOn
        self.fineCents = fineCents
    }

    func response(on db: Database) async throws -> LoanResponse {
        let book = try await $book.get(on: db)
        let user = try await $user.get(on: db)
        return LoanResponse(
            id: try requireID(),
            userId: $user.id,
            bookId: $book.id,
            borrowedOn: borrowedOn,
            dueOn: dueOn,
            returnedOn: returnedOn,
            fineCents: fineCents,
            book: LoanBook(id: try book.requireID(), title: book.title, isbn: book.isbn),
            user: LoanUser(id: try user.requireID(), email: user.email)
        )
    }
}
