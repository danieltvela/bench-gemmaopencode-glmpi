import Fluent
import Vapor

/// Loan, fine, and quota rules, kept out of the controllers.
enum LoanService {
    static let maxOpenLoansPerUser = 3
    static let loanPeriodDays = 14
    static let fineCentsPerDay = 50

    static func openLoanCount(for user: User, on db: Database) async throws -> Int {
        try await Loan.query(on: db)
            .filter(\.$user.$id == user.requireID())
            .filter(\.$returnedOn == nil)
            .count()
    }

    static func openLoanCount(for book: Book, on db: Database) async throws -> Int {
        try await Loan.query(on: db)
            .filter(\.$book.$id == book.requireID())
            .filter(\.$returnedOn == nil)
            .count()
    }

    static func availableCopies(for book: Book, on db: Database) async throws -> Int {
        let open = try await openLoanCount(for: book, on: db)
        return max(0, book.totalCopies - open)
    }

    static func borrow(user: User, book: Book, today: Date, on db: Database) async throws -> Loan {
        guard try await openLoanCount(for: user, on: db) < maxOpenLoansPerUser else {
            throw AppError.loanLimit
        }
        let openForBook = try await openLoanCount(for: book, on: db)
        guard openForBook < book.totalCopies else {
            throw AppError.noCopies
        }
        let loan = Loan(
            userID: try user.requireID(),
            bookID: try book.requireID(),
            borrowedOn: today,
            dueOn: Clock.addingDays(loanPeriodDays, to: today),
            returnedOn: nil,
            fineCents: 0
        )
        try await loan.save(on: db)
        return loan
    }

    static func returnLoan(_ loan: Loan, today: Date, on db: Database) async throws -> Loan {
        guard loan.returnedOn == nil else {
            throw AppError.alreadyReturned
        }
        let overdueDays = Clock.daysBetween(loan.dueOn, today)
        loan.returnedOn = today
        loan.fineCents = overdueDays > 0 ? fineCentsPerDay * overdueDays : 0
        try await loan.save(on: db)
        return loan
    }
}
