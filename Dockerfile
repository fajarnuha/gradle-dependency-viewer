FROM eclipse-temurin:21-jdk-jammy AS builder
WORKDIR /app
COPY gradlew gradlew.bat settings.gradle.kts build.gradle.kts gradle.properties ./
COPY gradle ./gradle
COPY core ./core
COPY server ./server
COPY app ./app
RUN --mount=type=cache,target=/root/.gradle \
    ./gradlew --no-daemon :core:jvmTest :server:test :server:installDist

FROM eclipse-temurin:21-jre-jammy
RUN groupadd --gid 10001 viewer && useradd --uid 10001 --gid viewer --no-create-home viewer
WORKDIR /app
COPY --from=builder /app/server/build/install/gradle-dependency-viewer/ ./
ENV PORT=8000 JAVA_OPTS="-XX:MaxRAMPercentage=75.0 -XX:+ExitOnOutOfMemoryError"
USER viewer
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl --fail --silent http://127.0.0.1:${PORT}/healthz || exit 1
ENTRYPOINT ["/app/bin/gradle-dependency-viewer"]
