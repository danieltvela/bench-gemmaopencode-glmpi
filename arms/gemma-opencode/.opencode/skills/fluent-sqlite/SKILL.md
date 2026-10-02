---
name: fluent-sqlite
description: Use when defining Fluent models, migrations, relations, or queries backed by SQLite, including pagination, aggregates and persistence across restarts. Covers Fluent 4 async APIs and the fluent-sqlite-driver.
---

# Fluent 4 + SQLite

## Setup

```swift
app.databases.use(.sqlite(.file(app.directory.workingDirectory + "shelf.sqlite")), as: .sqlite)
app.migrations.add(CreateUser())
try await app.autoMigrate()
```

The file is created on first boot; migrations must be idempotent. Seed initial
rows only when the table is empty (`Model.query(on: app.db).count() == 0`).

## Models

```swift
final class User: Model, @unchecked Sendable {
    static let schema = "users"
    @ID(key: .id) var id: UUID?
    @Field(key: "email") var email: String
    @OptionalField(key: "returned_on") var returnedOn: Date?
    @Timestamp(key: "created_at", on: .create) var createdAt: Date?
    @Parent(key: "user_id") var user: User     // set with $user.id = uuid
    init() {}
}
```

Migrations use `AsyncMigration` with `database.schema("users").id()
.field(...).unique(on: "email").create()`; reference other tables with
`.references("users", "id")`.

## Queries

- Filter: `.filter(\.$email == value)`, substring `.filter(\.$title ~~ text)`
  (SQLite `LIKE`, case-insensitive for ASCII), optional nil
  `.filter(\.$returnedOn == nil)`.
- Aggregates: `.count()`, `.sum(\.$fineCents) ?? 0`.
- Pagination: `.sort(\.$title, .ascending).range(offset ..< (offset + per)).all()`.
- Eager load relations with `.with(\.$book)`, then `try loan.$book.get(on: db)`.
- Derive values (counts, availability) from queries instead of storing
  denormalized columns unless the contract demands stored money fields.

## Gotchas

- `requireID()` throws when the model is unsaved; use `try`.
- Mutating and saving an optional field: assign then `try await model.save(on: db)`.
- `@Timestamp` is set by Fluent; do not manage it manually.
- SQLite has no case-insensitive unique by default: normalize before saving and
  enforce `unique(on:)`.
