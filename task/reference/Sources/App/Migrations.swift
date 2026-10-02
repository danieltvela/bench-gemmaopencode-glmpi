import Fluent

struct CreateUser: AsyncMigration {
    func prepare(on database: Database) async throws {
        try await database.schema("users")
            .id()
            .field("email", .string, .required)
            .field("password_hash", .string, .required)
            .field("name", .string, .required)
            .field("role", .string, .required)
            .field("created_at", .datetime)
            .unique(on: "email")
            .create()
    }

    func revert(on database: Database) async throws {
        try await database.schema("users").delete()
    }
}

struct CreateBook: AsyncMigration {
    func prepare(on database: Database) async throws {
        try await database.schema("books")
            .id()
            .field("isbn", .string, .required)
            .field("title", .string, .required)
            .field("author", .string, .required)
            .field("total_copies", .int, .required)
            .field("created_at", .datetime)
            .unique(on: "isbn")
            .create()
    }

    func revert(on database: Database) async throws {
        try await database.schema("books").delete()
    }
}

struct CreateLoan: AsyncMigration {
    func prepare(on database: Database) async throws {
        try await database.schema("loans")
            .id()
            .field("user_id", .uuid, .required, .references("users", "id"))
            .field("book_id", .uuid, .required, .references("books", "id"))
            .field("borrowed_on", .datetime, .required)
            .field("due_on", .datetime, .required)
            .field("returned_on", .datetime)
            .field("fine_cents", .int, .required)
            .create()
    }

    func revert(on database: Database) async throws {
        try await database.schema("loans").delete()
    }
}
