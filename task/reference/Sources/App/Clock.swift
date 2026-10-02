import Vapor

enum Clock {
    static let utc = TimeZone(identifier: "UTC") ?? TimeZone(secondsFromGMT: 0)!

    private static var calendar: Calendar {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = utc
        return calendar
    }

    /// Server "today": UTC date unless the request carries X-Test-Date.
    static func today(_ request: Request) -> Date {
        if let raw = request.headers.first(name: "X-Test-Date"),
           let parsed = parseDay(raw) {
            return parsed
        }
        return calendar.startOfDay(for: Date())
    }

    static func parseDay(_ raw: String) -> Date? {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = utc
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter.date(from: raw)
    }

    static func addingDays(_ days: Int, to date: Date) -> Date {
        calendar.date(byAdding: .day, value: days, to: date) ?? date
    }

    static func daysBetween(_ start: Date, _ end: Date) -> Int {
        calendar.dateComponents(
            [.day],
            from: calendar.startOfDay(for: start),
            to: calendar.startOfDay(for: end)
        ).day ?? 0
    }
}
