import Vapor

struct AppError: AbortError {
    let status: HTTPResponseStatus
    let code: String
    let reason: String

    var identifier: String { code }

    static let validationFailed = AppError(
        status: .badRequest, code: "validation_failed", reason: "Validation failed"
    )
    static let unauthorized = AppError(
        status: .unauthorized, code: "unauthorized", reason: "Unauthorized"
    )
    static let forbidden = AppError(
        status: .forbidden, code: "forbidden", reason: "Forbidden"
    )
    static let notFound = AppError(
        status: .notFound, code: "not_found", reason: "Not found"
    )
    static let emailTaken = AppError(
        status: .conflict, code: "email_taken", reason: "Email already registered"
    )
    static let isbnTaken = AppError(
        status: .conflict, code: "conflict", reason: "ISBN already exists"
    )
    static let noCopies = AppError(
        status: .conflict, code: "no_copies", reason: "No copies available"
    )
    static let loanLimit = AppError(
        status: .conflict, code: "loan_limit", reason: "Open loan limit reached"
    )
    static let alreadyReturned = AppError(
        status: .conflict, code: "already_returned", reason: "Loan already returned"
    )
    static let bookHasOpenLoans = AppError(
        status: .conflict, code: "book_has_open_loans", reason: "Book has open loans"
    )
    static let copiesBelowOpenLoans = AppError(
        status: .conflict,
        code: "copies_below_open_loans",
        reason: "totalCopies cannot drop below open loans"
    )
}

final class AppErrorMiddleware: Middleware {
    func respond(to request: Request, chainingTo next: Responder) -> EventLoopFuture<Response> {
        next.respond(to: request).flatMapErrorThrowing { error in
            let status: HTTPResponseStatus
            let code: String
            let message: String
            if let appError = error as? AppError {
                status = appError.status
                code = appError.code
                message = appError.reason
            } else if let abort = error as? AbortError {
                status = abort.status
                switch abort.status {
                case .badRequest: code = "validation_failed"
                case .unauthorized: code = "unauthorized"
                case .forbidden: code = "forbidden"
                case .notFound: code = "not_found"
                case .conflict: code = "conflict"
                default: code = "internal_error"
                }
                message = abort.reason
            } else if error is DecodingError {
                status = .badRequest
                code = "validation_failed"
                message = "Invalid request body"
            } else {
                status = .internalServerError
                code = "internal_error"
                message = "Internal server error"
            }
            let response = Response(status: status)
            try response.content.encode(ErrorBody(error: message, code: code))
            return response
        }
    }
}
