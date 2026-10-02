FROM swift:6.1-jammy AS build
WORKDIR /build
COPY Package.swift ./
RUN swift package resolve
COPY Sources ./Sources
RUN swift build -c release

FROM swift:6.1-jammy
WORKDIR /app
COPY --from=build /build/.build/release/App ./
EXPOSE 8080
ENV PORT=8080
CMD ["./App", "serve", "--hostname", "0.0.0.0"]
