import Fluent
import FluentSQLiteDriver
import JWT
import Vapor

func configure(_ app: Application) async throws {
    app.http.server.configuration.hostname = "0.0.0.0"
    if let port = Environment.get("PORT").flatMap(Int.init) {
        app.http.server.configuration.port = port
    }

    let encoder = JSONEncoder()
    encoder.dateEncodingStrategy = .iso8601
    let decoder = JSONDecoder()
    decoder.dateDecodingStrategy = .iso8601
    ContentConfiguration.global.use(encoder: encoder, for: .json)
    ContentConfiguration.global.use(decoder: decoder, for: .json)

    let databasePath = app.directory.workingDirectory + "shelf.sqlite"
    app.databases.use(.sqlite(.file(databasePath)), as: .sqlite)

    app.migrations.add(CreateUser())
    app.migrations.add(CreateBook())
    app.migrations.add(CreateLoan())
    try await app.autoMigrate()

    let secret = Environment.get("JWT_SECRET") ?? "shelf-dev-secret"
    app.jwt.signers.use(.hs256(key: secret))

    app.middleware = .init()
    app.middleware.use(AppErrorMiddleware())

    if try await User.query(on: app.db).count() == 0 {
        let admin = User(
            email: "admin@shelf.test",
            passwordHash: try Bcrypt.hash("admin-pass"),
            name: "Admin",
            role: "admin"
        )
        try await admin.save(on: app.db)
    }

    try routes(app)
}
