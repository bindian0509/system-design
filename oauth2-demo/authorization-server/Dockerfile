# Build stage
FROM maven:3.9-eclipse-temurin-21-alpine AS build
WORKDIR /app

# Copy parent pom
COPY pom.xml ./
COPY authorization-server/pom.xml ./authorization-server/
COPY resource-server/pom.xml ./resource-server/

# Download dependencies
RUN mvn dependency:go-offline -pl authorization-server -am -B

# Copy source code
COPY authorization-server/src ./authorization-server/src

# Build the application
RUN mvn package -pl authorization-server -am -DskipTests -B

# Runtime stage
FROM eclipse-temurin:21-jre-alpine
WORKDIR /app

# Add non-root user for security
RUN addgroup -S spring && adduser -S spring -G spring
USER spring:spring

# Copy the built jar
COPY --from=build /app/authorization-server/target/*.jar app.jar

# Expose port
EXPOSE 9000

# Health check
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=5 \
  CMD wget -q --spider http://localhost:9000/actuator/health || exit 1

# Run the application
ENTRYPOINT ["java", "-jar", "app.jar"]
