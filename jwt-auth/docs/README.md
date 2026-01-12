# JWT Authentication with Access and Refresh Tokens

A simple Spring Boot application demonstrating JWT-based authentication with access tokens and refresh tokens using Spring Security and MySQL.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Token Flow](#token-flow)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Setup Instructions](#setup-instructions)
- [API Endpoints](#api-endpoints)
- [Usage Examples](#usage-examples)
- [Configuration](#configuration)
- [Security Considerations](#security-considerations)

---

## Architecture Overview

```mermaid
flowchart TB
    subgraph client [Client]
        A[HTTP Request]
    end

    subgraph security [Security Layer]
        B[JwtAuthenticationFilter]
        C[AuthenticationManager]
    end

    subgraph controllers [Controllers]
        D[AuthController]
        E[Protected Endpoints]
    end

    subgraph services [Services]
        F[AuthService]
        G[JwtService]
        H[RefreshTokenService]
    end

    subgraph database [MySQL Database]
        I[(users)]
        J[(refresh_tokens)]
    end

    A --> B
    B --> C
    C --> D
    C --> E
    D --> F
    F --> G
    F --> H
    H --> J
    G --> I
```

### Components

| Component | Description |
|-----------|-------------|
| **JwtAuthenticationFilter** | Intercepts requests, extracts JWT from Authorization header, validates token |
| **AuthController** | REST endpoints for register, login, refresh, logout |
| **AuthService** | Business logic for authentication operations |
| **JwtService** | JWT token generation, validation, and claim extraction |
| **RefreshTokenService** | Manages refresh token lifecycle in database |

---

## Token Flow

### Login Flow

```mermaid
sequenceDiagram
    participant C as Client
    participant A as AuthController
    participant S as AuthService
    participant J as JwtService
    participant DB as MySQL

    C->>A: POST /api/auth/login
    Note right of C: email, password
    A->>S: login(credentials)
    S->>DB: Validate user credentials
    DB-->>S: User data
    S->>J: generateAccessToken(user)
    J-->>S: Access Token (15 min)
    S->>J: createRefreshToken(user)
    J->>DB: Store refresh token
    J-->>S: Refresh Token (7 days)
    S-->>A: AuthResponse
    A-->>C: access_token + refresh_token
```

### Token Refresh Flow

```mermaid
sequenceDiagram
    participant C as Client
    participant A as AuthController
    participant S as AuthService
    participant R as RefreshTokenService
    participant J as JwtService
    participant DB as MySQL

    C->>A: POST /api/auth/refresh
    Note right of C: refreshToken
    A->>S: refreshToken(token)
    S->>R: findByToken(token)
    R->>DB: Query refresh_tokens
    DB-->>R: RefreshToken entity
    R-->>S: RefreshToken
    S->>R: verifyRefreshToken()
    R-->>S: Valid
    S->>J: generateAccessToken(user)
    J-->>S: New Access Token
    S-->>A: AuthResponse
    A-->>C: new access_token
```

### Logout Flow

```mermaid
sequenceDiagram
    participant C as Client
    participant A as AuthController
    participant S as AuthService
    participant R as RefreshTokenService
    participant DB as MySQL

    C->>A: POST /api/auth/logout
    Note right of C: refreshToken + Authorization header
    A->>S: logout(refreshToken)
    S->>R: revokeRefreshToken(token)
    R->>DB: Set revoked=true
    DB-->>R: Updated
    R-->>S: Success
    S-->>A: Success
    A-->>C: "Logged out successfully"
```

---

## Project Structure

```
jwt-auth/
├── src/main/java/com/example/jwtauth/
│   ├── config/
│   │   └── SecurityConfig.java          # Spring Security configuration
│   ├── controller/
│   │   └── AuthController.java          # REST API endpoints
│   ├── dto/
│   │   ├── AuthResponse.java            # Response with tokens
│   │   ├── LoginRequest.java            # Login request body
│   │   ├── RefreshRequest.java          # Refresh token request
│   │   └── RegisterRequest.java         # Registration request body
│   ├── entity/
│   │   ├── RefreshToken.java            # Refresh token JPA entity
│   │   └── User.java                    # User JPA entity
│   ├── repository/
│   │   ├── RefreshTokenRepository.java  # Refresh token data access
│   │   └── UserRepository.java          # User data access
│   ├── security/
│   │   └── JwtAuthenticationFilter.java # JWT filter for requests
│   ├── service/
│   │   ├── AuthService.java             # Authentication business logic
│   │   ├── JwtService.java              # JWT operations
│   │   ├── RefreshTokenService.java     # Refresh token management
│   │   └── UserDetailsServiceImpl.java  # Spring Security UserDetailsService
│   └── JwtAuthApplication.java          # Main application class
├── src/main/resources/
│   └── application.yml                  # Configuration file
├── docs/
│   └── README.md                        # This documentation
├── docker-compose.yml                   # MySQL container setup
└── pom.xml                              # Maven dependencies
```

---

## Prerequisites

- **Java 17** or higher
- **Maven 3.6+**
- **Docker** (for MySQL) or local MySQL installation

---

## Setup Instructions

### Option 1: Docker (Recommended)

Run everything with a single command:

```bash
cd jwt-auth

# Build and start all services (MySQL + App)
docker-compose up -d --build

# View logs
docker-compose logs -f app

# Stop all services
docker-compose down
```

This starts:
- **MySQL** on port 3306
- **Spring Boot App** on port 8080

### Option 2: Local Development

If you prefer running the app locally:

```bash
# Start only MySQL
docker-compose up -d mysql

# Run the app locally
./mvnw spring-boot:run
```

### Verify Setup

```bash
curl http://localhost:8080/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123"}'
```

You should receive a response with `accessToken` and `refreshToken`.

---

## API Endpoints

| Endpoint | Method | Auth Required | Description |
|----------|--------|---------------|-------------|
| `/api/auth/register` | POST | No | Register a new user |
| `/api/auth/login` | POST | No | Login and get tokens |
| `/api/auth/refresh` | POST | No | Refresh access token |
| `/api/auth/logout` | POST | Yes | Invalidate refresh token |
| `/api/auth/me` | GET | Yes | Test protected endpoint |

---

## Usage Examples

### Register a New User

```bash
curl -X POST http://localhost:8080/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securepassword123"
  }'
```

**Response:**

```json
{
  "accessToken": "eyJhbGciOiJIUzI1NiJ9...",
  "refreshToken": "550e8400-e29b-41d4-a716-446655440000",
  "tokenType": "Bearer"
}
```

### Login

```bash
curl -X POST http://localhost:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securepassword123"
  }'
```

**Response:**

```json
{
  "accessToken": "eyJhbGciOiJIUzI1NiJ9...",
  "refreshToken": "550e8400-e29b-41d4-a716-446655440001",
  "tokenType": "Bearer"
}
```

### Access Protected Endpoint

```bash
curl -X GET http://localhost:8080/api/auth/me \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9..."
```

**Response:**

```json
{
  "message": "You are authenticated!"
}
```

### Refresh Access Token

When your access token expires (after 15 minutes), use the refresh token to get a new one:

```bash
curl -X POST http://localhost:8080/api/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{
    "refreshToken": "550e8400-e29b-41d4-a716-446655440001"
  }'
```

**Response:**

```json
{
  "accessToken": "eyJhbGciOiJIUzI1NiJ9...(new token)",
  "refreshToken": "550e8400-e29b-41d4-a716-446655440001",
  "tokenType": "Bearer"
}
```

### Logout

```bash
curl -X POST http://localhost:8080/api/auth/logout \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9..." \
  -H "Content-Type: application/json" \
  -d '{
    "refreshToken": "550e8400-e29b-41d4-a716-446655440001"
  }'
```

**Response:**

```json
{
  "message": "Logged out successfully"
}
```

---

## Configuration

Configuration is in `src/main/resources/application.yml`:

```yaml
# Server Configuration
server:
  port: 8080

# Database Configuration
spring:
  datasource:
    url: jdbc:mysql://localhost:3306/jwt_auth_db
    username: root
    password: root

# JWT Configuration
jwt:
  secret: <base64-encoded-secret-key>
  access-token-expiration: 900000      # 15 minutes
  refresh-token-expiration: 604800000  # 7 days
```

### Environment Variables

You can override configuration using environment variables:

```bash
export SPRING_DATASOURCE_URL=jdbc:mysql://your-host:3306/your_db
export SPRING_DATASOURCE_USERNAME=your_user
export SPRING_DATASOURCE_PASSWORD=your_password
export JWT_SECRET=your-256-bit-secret-key
```

---

## Security Considerations

### Token Storage

| Token Type | Storage Location | Why |
|------------|------------------|-----|
| Access Token | Client memory/localStorage | Short-lived, less risk if leaked |
| Refresh Token | httpOnly cookie (production) | Long-lived, stored securely in DB |

### Best Practices

1. **Use HTTPS in production** - Tokens are transmitted in headers
2. **Store refresh tokens securely** - Use httpOnly cookies
3. **Use strong JWT secret** - At least 256 bits
4. **Implement token rotation** - Issue new refresh token on refresh
5. **Add rate limiting** - Prevent brute force attacks

### Token Expiration Strategy

```
Access Token:  15 minutes  → Frequent rotation, minimal exposure
Refresh Token: 7 days      → Stored in DB, can be revoked
```

---

## Database Schema

### users table

| Column | Type | Description |
|--------|------|-------------|
| id | BIGINT | Primary key, auto-increment |
| email | VARCHAR(255) | Unique email address |
| password | VARCHAR(255) | BCrypt hashed password |
| created_at | DATETIME | Account creation timestamp |

### refresh_tokens table

| Column | Type | Description |
|--------|------|-------------|
| id | BIGINT | Primary key, auto-increment |
| token | VARCHAR(255) | Unique refresh token (UUID) |
| user_id | BIGINT | Foreign key to users |
| expiry_date | DATETIME | Token expiration timestamp |
| revoked | BOOLEAN | Whether token is revoked |

---

## Troubleshooting

### Common Issues

**1. MySQL Connection Refused**

```bash
# Check if MySQL is running
docker ps

# Restart MySQL container
docker-compose down && docker-compose up -d
```

**2. Invalid JWT Token**

- Ensure the token hasn't expired
- Check that you're using the correct `Authorization: Bearer <token>` format
- Verify the JWT secret matches in both generation and validation

**3. User Already Exists**

- The email must be unique
- Use a different email or check your database

---

## License

MIT License
