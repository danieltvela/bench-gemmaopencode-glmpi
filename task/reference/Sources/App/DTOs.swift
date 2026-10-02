import Vapor

struct HealthResponse: Content {
    let status: String
}

struct PublicUser: Content {
    let id: UUID
    let email: String
    let name: String
    let role: String
}

struct AuthResponse: Content {
    let id: UUID
    let email: String
    let name: String
    let role: String
    let token: String
}

struct BookResponse: Content {
    let id: UUID
    let isbn: String
    let title: String
    let author: String
    let totalCopies: Int
    let availableCopies: Int
    let createdAt: Date
}

struct BookListResponse: Content {
    let items: [BookResponse]
    let page: Int
    let per: Int
    let total: Int
}

struct LoanBook: Content {
    let id: UUID
    let title: String
    let isbn: String
}

struct LoanUser: Content {
    let id: UUID
    let email: String
}

struct LoanResponse: Content {
    let id: UUID
    let userId: UUID
    let bookId: UUID
    let borrowedOn: Date
    let dueOn: Date
    let returnedOn: Date?
    let fineCents: Int
    let book: LoanBook
    let user: LoanUser

    enum CodingKeys: String, CodingKey {
        case id, userId, bookId, borrowedOn, dueOn, returnedOn, fineCents, book, user
    }

    // Encode nil as JSON null (synthesized Codable would omit the key).
    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(id, forKey: .id)
        try container.encode(userId, forKey: .userId)
        try container.encode(bookId, forKey: .bookId)
        try container.encode(borrowedOn, forKey: .borrowedOn)
        try container.encode(dueOn, forKey: .dueOn)
        try container.encode(returnedOn, forKey: .returnedOn)
        try container.encode(fineCents, forKey: .fineCents)
        try container.encode(book, forKey: .book)
        try container.encode(user, forKey: .user)
    }
}

struct LoanListResponse: Content {
    let items: [LoanResponse]
    let page: Int
    let per: Int
    let total: Int
}

struct StatsResponse: Content {
    let users: Int
    let books: Int
    let openLoans: Int
    let totalFinesCents: Int
}

struct ErrorBody: Content {
    let error: String
    let code: String
}
