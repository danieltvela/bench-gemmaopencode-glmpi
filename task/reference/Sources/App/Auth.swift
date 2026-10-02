import Fluent
import JWT
import Vapor

struct UserToken: JWTPayload {
    var sub: SubjectClaim
    var iat: IssuedAtClaim
    var exp: ExpirationClaim

    func verify(using signer: JWTSigner) throws {
        try exp.verifyNotExpired()
    }
}

enum Auth {
    static func token(for user: User, app: Application) throws -> String {
        let payload = UserToken(
            sub: SubjectClaim(value: try user.requireID().uuidString),
            iat: IssuedAtClaim(value: Date()),
            exp: ExpirationClaim(value: Date().addingTimeInterval(3600))
        )
        return try app.jwt.signers.sign(payload)
    }

    static func requireUser(_ request: Request, role: String? = nil) async throws -> User {
        guard let token = request.headers.bearerAuthorization?.token else {
            throw AppError.unauthorized
        }
        guard let payload = try? request.jwt.verify(token, as: UserToken.self) else {
            throw AppError.unauthorized
        }
        guard let id = UUID(uuidString: payload.sub.value) else {
            throw AppError.unauthorized
        }
        guard let user = try await User.find(id, on: request.db) else {
            throw AppError.unauthorized
        }
        if let role, user.role != role {
            throw AppError.forbidden
        }
        return user
    }
}
