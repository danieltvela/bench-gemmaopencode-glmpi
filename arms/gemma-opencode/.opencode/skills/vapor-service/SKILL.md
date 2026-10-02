---
name: vapor-service
description: Use when implementing or debugging a Vapor 4 web service on Linux: entrypoint, configure, routes, JSON DTOs, error shapes, bearer auth/JWT and request handling. Covers the Vapor 4 async APIs and vapor/jwt 4.x.
---

# Vapor 4 service

## Entrypoint

```swift
@main
enum Entrypoint {
    static func main() async throws {
        var env = try Environment.detect()
        try LoggingSystem.bootstrap(from: &env)
        let app = try await Application.make(env)
        do {
            try await configure(app)
            try await app.execute()
        } catch {
            app.logger.report(error: error)
            try? await app.asyncShutdown()
            throw error
        }
        try await app.asyncShutdown()
    }
}
```

`Application(env)`/`app.run()` still compile but are deprecated in async
contexts; use `Application.make`/`execute`/`asyncShutdown`.

## configure

- Read `PORT` and `JWT_SECRET` from `Environment.get` and apply defaults.
- Set `app.http.server.configuration.hostname = "0.0.0.0"`.
- Configure JSON once for ISO-8601 dates and timezones:

```swift
let encoder = JSONEncoder(); encoder.dateEncodingStrategy = .iso8601
let decoder = JSONDecoder(); decoder.dateDecodingStrategy = .iso8601
ContentConfiguration.global.use(encoder: encoder, for: .json)
ContentConfiguration.global.use(decoder: decoder, for: .json)
```

- Swift's synthesized Codable **omits nil optionals**. If a response contract
  requires an explicit `"field": null`, implement `encode(to:)` with
  `container.encode(optional, forKey:)`.

## Routes and DTOs

- Handlers are `async throws` closures or functions; group with
  `app.grouped("auth")`.
- Bodies/params are `Codable` structs conforming to `Content`; decode with
  `try req.content.decode(Body.self)`.
- Return `Response` with `encodeResponse(status:for:)` when a non-200 status is
  needed; `HTTPStatus` (e.g. `.noContent`) otherwise.
- Query params: `req.query[Int.self, at: "page"]`.

## Error shape

Default Vapor errors serialize as `{"error":true,"reason":...}`. When the
contract fixes `{"error": string, "code": string}`, define an `AbortError` with
a `code`, throw it for business errors, and install a middleware that maps
errors to that JSON envelope (bad request -> validation code, unauthorized,
forbidden, not found, conflict). Replace `app.middleware` with your own
instance so the default error middleware cannot intercept first.

## JWT (vapor/jwt 4.x)

```swift
import JWT

struct UserToken: JWTPayload {
    var sub: SubjectClaim
    var iat: IssuedAtClaim
    var exp: ExpirationClaim
    func verify(using signer: JWTSigner) throws { try exp.verifyNotExpired() }
}

app.jwt.signers.use(.hs256(key: secret))          // secret: String works
let token = try app.jwt.signers.sign(payload)
let payload = try req.jwt.verify(token, as: UserToken.self)
```

- Bearer header: `req.headers.bearerAuthorization?.token`.
- Passwords: `Bcrypt.hash` / `Bcrypt.verify` from Vapor.
- Authentication failures return 401; authenticated-but-not-allowed returns
  403. Do not use 401 for authorization errors.

## Self-checking

Prefer an in-process test (`app.testable(.router)` with XCTVapor) for route
logic, but remember the external grader runs the process over HTTP: the
package must build and boot on its own.
