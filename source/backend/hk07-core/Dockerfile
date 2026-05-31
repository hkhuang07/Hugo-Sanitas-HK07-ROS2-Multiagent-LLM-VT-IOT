# ─── Stage 1: Build (Maven) ───────────────────────────────────────────────────
FROM eclipse-temurin:21-jdk-alpine AS builder
WORKDIR /build

# Copy dependency declarations first (Docker layer cache optimization)
COPY pom.xml .
# Download dependencies once; won't re-download if pom.xml unchanged
RUN mvn dependency:go-offline -B -q 2>/dev/null || true

# Copy source and build
COPY src ./src
# Single-threaded build to protect 1.6GHz CPU (hardware constraint)
RUN mvn clean package -DskipTests -T 1 -B -q

# ─── Stage 2: Runtime (Minimal JRE) ──────────────────────────────────────────
FROM eclipse-temurin:21-jre-alpine AS runtime

# Non-root user for security (Bootrom philosophy)
RUN addgroup -S hk07 && adduser -S hk07 -G hk07
USER hk07

WORKDIR /app
COPY --from=builder /build/target/hk07-core-*.jar app.jar

# Expose REST + WebSocket port
EXPOSE 8888

# ─── Hardware-constrained JVM flags ───────────────────────────────────────────
# -Xms256m        : Initial heap 256MB (prevents over-allocation on startup)
# -Xmx512m        : Hard cap at 512MB (leaves room for other services on 8GB host)
# -XX:+UseG1GC    : G1 garbage collector (better pause time than default)
# -XX:MaxGCPauseMillis=50 : Target GC pauses under 50ms (60Hz sensor streams)
# -Dfile.encoding : Ensure UTF-8 for Vietnamese text support
ENTRYPOINT ["java", \
  "-Xms256m", "-Xmx512m", \
  "-XX:+UseG1GC", "-XX:MaxGCPauseMillis=50", \
  "-Dfile.encoding=UTF-8", \
  "-Dspring.profiles.active=docker", \
  "-jar", "app.jar"]

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD wget -qO- http://localhost:8888/api/v1/health || exit 1
