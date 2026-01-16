# Build stage
FROM eclipse-temurin:21-jdk-alpine AS build
WORKDIR /app

# Install Maven
RUN apk add --no-cache maven

# Copy parent pom
COPY pom.xml ./pom.xml

# Create module directories
RUN mkdir -p authorization-server resource-server

# Copy module poms
COPY authorization-server/pom.xml ./authorization-server/pom.xml
COPY resource-server/pom.xml ./resource-server/pom.xml

# Download dependencies (cached layer)
RUN mvn dependency:go-offline -B -pl authorization-server -am || true

# Copy source code for authorization-server only
COPY authorization-server/src ./authorization-server/src

# Build the authorization-server module
RUN mvn clean package -DskipTests -pl authorization-server -am

# Runtime stage
FROM eclipse-temurin:21-jre-alpine
WORKDIR /app

# Install wget for health checks
RUN apk add --no-cache wget

# Copy the JAR from build stage
COPY --from=build /app/authorization-server/target/*.jar app.jar

# Expose port
EXPOSE 9000

# Run the application
ENTRYPOINT ["java", "-jar", "app.jar"]
