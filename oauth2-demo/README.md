# OAuth 2.0 Demo - Spring Boot Implementation

A complete OAuth 2.0 implementation featuring a **Spring Authorization Server** and a **Resource Server**, supporting multiple grant types with PostgreSQL persistence.

## Architecture

```
┌─────────────────────┐     ┌─────────────────────────────┐     ┌──────────────────────┐
│    OAuth Clients    │────▶│   Authorization Server      │     │   Resource Server    │
│  (Web, SPA, Service)│     │        (Port 9000)          │     │     (Port 8080)      │
└─────────────────────┘     │                             │     │                      │
                            │  /oauth2/authorize          │     │  /api/public/**      │
                            │  /oauth2/token              │     │  /api/protected      │
                            │  /oauth2/jwks               │     │  /api/user           │
                            │  /userinfo                  │     │  /api/admin/**       │
                            └──────────────┬──────────────┘     └──────────┬───────────┘
                                           │                               │
                                           │     ┌────────────────┐        │
                                           └────▶│   PostgreSQL   │◀───────┘
                                                 │   (Port 5432)  │  (JWKS validation)
                                                 └────────────────┘
```

## Features

- **Authorization Code Grant** - For web applications with server-side backend
- **Authorization Code + PKCE** - For SPAs and mobile apps (public clients)
- **Client Credentials Grant** - For machine-to-machine communication
- **Refresh Token Grant** - For token renewal
- **JWT Access Tokens** - With custom claims (authorities, username)
- **PostgreSQL Persistence** - Users, OAuth clients, and authorizations
- **Role-Based Access Control** - USER and ADMIN roles
- **Fully Dockerized** - One command to run everything

## Prerequisites

- Docker & Docker Compose

## Quick Start (Docker - Recommended)

Run everything with a single command:

```bash
./run.sh
```

This will:
1. Build both Spring Boot applications
2. Start PostgreSQL, Authorization Server, and Resource Server
3. Wait for all services to be healthy
4. Display connection info and test commands

### Other Commands

```bash
./run.sh start    # Start all services (default)
./run.sh stop     # Stop all services
./run.sh restart  # Restart all services
./run.sh logs     # View service logs
./run.sh status   # Show service status
./run.sh clean    # Stop and remove volumes
./run.sh test     # Run OAuth flow tests
```

## Manual Start (Development)

If you prefer to run without Docker:

### 1. Start PostgreSQL

```bash
docker-compose up -d postgres
```

### 2. Build the Project

```bash
mvn clean install
```

### 3. Start Authorization Server (Port 9000)

```bash
cd authorization-server
mvn spring-boot:run
```

### 4. Start Resource Server (Port 8080)

In a new terminal:

```bash
cd resource-server
mvn spring-boot:run
```

## Demo Credentials

### Users
| Username | Password | Roles |
|----------|----------|-------|
| user     | password | USER  |
| admin    | password | USER, ADMIN |

### OAuth Clients
| Client ID | Client Secret | Grant Types | Use Case |
|-----------|---------------|-------------|----------|
| web-client | secret | Authorization Code, Refresh Token | Web apps with backend |
| spa-client | (none - public) | Authorization Code + PKCE, Refresh Token | SPAs, Mobile apps |
| service-client | secret | Client Credentials | Service-to-service |

## Testing the OAuth Flows

### 1. Client Credentials Flow (Machine-to-Machine)

Get an access token using client credentials:

```bash
# Base64 encode "service-client:secret" = c2VydmljZS1jbGllbnQ6c2VjcmV0
curl -X POST http://localhost:9000/oauth2/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -H "Authorization: Basic c2VydmljZS1jbGllbnQ6c2VjcmV0" \
  -d "grant_type=client_credentials&scope=read write"
```

Response:
```json
{
  "access_token": "eyJraWQiOi...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "scope": "read write"
}
```

### 2. Authorization Code Flow (Web Application)

#### Step 1: Get Authorization Code

Open in browser:
```
http://localhost:9000/oauth2/authorize?response_type=code&client_id=web-client&redirect_uri=http://localhost:3000/callback&scope=openid profile read write
```

1. Login with `user` / `password`
2. Approve the consent screen
3. Copy the `code` from the redirect URL

#### Step 2: Exchange Code for Tokens

```bash
# Replace CODE_HERE with the authorization code
# Base64 encode "web-client:secret" = d2ViLWNsaWVudDpzZWNyZXQ=
curl -X POST http://localhost:9000/oauth2/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -H "Authorization: Basic d2ViLWNsaWVudDpzZWNyZXQ=" \
  -d "grant_type=authorization_code&code=CODE_HERE&redirect_uri=http://localhost:3000/callback"
```

### 3. Authorization Code + PKCE Flow (SPA/Mobile)

#### Step 1: Generate PKCE Values

```bash
# Generate code_verifier (43-128 chars, URL-safe)
CODE_VERIFIER=$(openssl rand -base64 32 | tr -d '=' | tr '/+' '_-')
echo "Code Verifier: $CODE_VERIFIER"

# Generate code_challenge (SHA256 hash of verifier, base64url encoded)
CODE_CHALLENGE=$(echo -n "$CODE_VERIFIER" | openssl dgst -sha256 -binary | base64 | tr -d '=' | tr '/+' '_-')
echo "Code Challenge: $CODE_CHALLENGE"
```

#### Step 2: Get Authorization Code

Open in browser (replace CODE_CHALLENGE):
```
http://localhost:9000/oauth2/authorize?response_type=code&client_id=spa-client&redirect_uri=http://localhost:4200/callback&scope=openid profile read&code_challenge=CODE_CHALLENGE&code_challenge_method=S256
```

#### Step 3: Exchange Code for Tokens (No client secret needed!)

```bash
curl -X POST http://localhost:9000/oauth2/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=authorization_code&code=CODE_HERE&redirect_uri=http://localhost:4200/callback&client_id=spa-client&code_verifier=CODE_VERIFIER"
```

### 4. Refresh Token Flow

```bash
curl -X POST http://localhost:9000/oauth2/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -H "Authorization: Basic d2ViLWNsaWVudDpzZWNyZXQ=" \
  -d "grant_type=refresh_token&refresh_token=REFRESH_TOKEN_HERE"
```

## Testing Protected Resources

### Access Public Endpoints (No Auth Required)

```bash
curl http://localhost:8080/api/public/health
curl http://localhost:8080/api/public/info
```

### Access Protected Endpoints (Token Required)

```bash
# Use the access_token from any of the flows above
TOKEN="eyJraWQiOi..."

# Basic protected resource
curl http://localhost:8080/api/protected \
  -H "Authorization: Bearer $TOKEN"

# User info from JWT
curl http://localhost:8080/api/user \
  -H "Authorization: Bearer $TOKEN"

# Data endpoint (requires 'read' scope)
curl http://localhost:8080/api/data \
  -H "Authorization: Bearer $TOKEN"

# Write access check (requires 'write' scope)
curl http://localhost:8080/api/data/write-check \
  -H "Authorization: Bearer $TOKEN"
```

### Access Admin Endpoints (ADMIN Role Required)

Login as `admin` and get a token:

```bash
# Admin dashboard
curl http://localhost:8080/api/admin/dashboard \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# Admin settings (requires ADMIN role + admin scope)
# Use service-client with admin scope for this
curl http://localhost:8080/api/admin/settings \
  -H "Authorization: Bearer $SERVICE_TOKEN_WITH_ADMIN_SCOPE"
```

## API Endpoints Reference

### Authorization Server (Port 9000)

| Endpoint | Description |
|----------|-------------|
| `/oauth2/authorize` | Authorization endpoint (interactive login) |
| `/oauth2/token` | Token endpoint (get/refresh tokens) |
| `/oauth2/jwks` | JSON Web Key Set for JWT validation |
| `/oauth2/revoke` | Revoke tokens |
| `/oauth2/introspect` | Token introspection |
| `/userinfo` | OpenID Connect user info |
| `/.well-known/openid-configuration` | OpenID Connect discovery |
| `/login` | Login page |

### Resource Server (Port 8080)

| Endpoint | Auth Required | Scope/Role |
|----------|---------------|------------|
| `GET /api/public/health` | No | - |
| `GET /api/public/info` | No | - |
| `GET /api/protected` | Yes | Any valid token |
| `GET /api/user` | Yes | Any valid token |
| `GET /api/data` | Yes | `read` scope |
| `GET /api/data/write-check` | Yes | `write` scope |
| `GET /api/admin/dashboard` | Yes | `ADMIN` role |
| `GET /api/admin/settings` | Yes | `ADMIN` role + `admin` scope |

## Project Structure

```
oauth2-demo/
├── docker-compose.yml              # PostgreSQL setup
├── pom.xml                         # Parent POM
├── init-scripts/                   # Docker DB initialization
│   └── 01-init.sql
├── authorization-server/           # OAuth 2.0 Authorization Server
│   ├── pom.xml
│   └── src/main/
│       ├── java/com/oauth/authserver/
│       │   ├── AuthServerApplication.java
│       │   ├── config/
│       │   │   ├── AuthorizationServerConfig.java
│       │   │   ├── SecurityConfig.java
│       │   │   └── WebConfig.java
│       │   ├── entity/
│       │   │   ├── User.java
│       │   │   └── Role.java
│       │   ├── repository/
│       │   │   └── UserRepository.java
│       │   └── service/
│       │       └── CustomUserDetailsService.java
│       └── resources/
│           ├── application.yml
│           ├── schema.sql
│           ├── data.sql
│           └── templates/
│               └── login.html
└── resource-server/                # OAuth 2.0 Resource Server
    ├── pom.xml
    └── src/main/
        ├── java/com/oauth/resourceserver/
        │   ├── ResourceServerApplication.java
        │   ├── config/
        │   │   └── ResourceServerConfig.java
        │   └── controller/
        │       └── ProtectedResourceController.java
        └── resources/
            └── application.yml
```

## Configuration

### Authorization Server (`authorization-server/src/main/resources/application.yml`)

```yaml
server:
  port: 9000

spring:
  datasource:
    url: jdbc:postgresql://localhost:5432/oauth2db
    username: oauth2user
    password: oauth2pass
```

### Resource Server (`resource-server/src/main/resources/application.yml`)

```yaml
server:
  port: 8080

spring:
  security:
    oauth2:
      resourceserver:
        jwt:
          issuer-uri: http://localhost:9000
          jwk-set-uri: http://localhost:9000/oauth2/jwks
```

## Troubleshooting

### Database Connection Issues
```bash
# Check if PostgreSQL is running
docker-compose ps

# View PostgreSQL logs
docker-compose logs postgres

# Reset database
docker-compose down -v
docker-compose up -d
```

### JWT Validation Errors
- Ensure Authorization Server is running before Resource Server
- Check that the issuer-uri matches the Authorization Server's configured issuer
- Verify the token hasn't expired

### CORS Issues
- Check that your client's origin is in the allowed origins list
- Resource Server allows: `localhost:3000`, `localhost:4200`

## License

MIT License
