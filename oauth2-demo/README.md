# OAuth 2.0 Demo - Spring Boot Implementation

A complete OAuth 2.0 implementation featuring a **Spring Authorization Server** and a **Resource Server**, supporting multiple grant types with PostgreSQL persistence.

## System Architecture

```mermaid
graph TB
    subgraph Clients [OAuth Clients]
        WebApp[Web Application]
        SPA[Single Page App]
        Service[Backend Service]
    end

    subgraph AuthServer [Authorization Server :9001]
        AuthEndpoint["/oauth2/authorize"]
        TokenEndpoint["/oauth2/token"]
        JWKSEndpoint["/oauth2/jwks"]
        LoginPage["/login"]
    end

    subgraph ResourceServer [Resource Server :8080]
        PublicAPI["/api/public/**"]
        ProtectedAPI["/api/protected"]
        AdminAPI["/api/admin/**"]
        JWTValidator[JWT Validator]
    end

    subgraph Database [PostgreSQL :5432]
        Users[(Users)]
        OAuthClients[(OAuth Clients)]
        Authorizations[(Authorizations)]
    end

    WebApp -->|1. Auth Code Flow| AuthEndpoint
    SPA -->|2. Auth Code + PKCE| AuthEndpoint
    Service -->|3. Client Credentials| TokenEndpoint

    AuthEndpoint -->|Login Required| LoginPage
    LoginPage -->|Authenticated| AuthEndpoint
    AuthEndpoint -->|Auth Code| WebApp
    AuthEndpoint -->|Auth Code| SPA

    WebApp -->|Exchange Code| TokenEndpoint
    SPA -->|Exchange Code + Verifier| TokenEndpoint
    TokenEndpoint -->|JWT Access Token| WebApp
    TokenEndpoint -->|JWT Access Token| SPA
    TokenEndpoint -->|JWT Access Token| Service

    WebApp -->|Bearer Token| ProtectedAPI
    SPA -->|Bearer Token| ProtectedAPI
    Service -->|Bearer Token| AdminAPI

    JWTValidator -->|Fetch Public Keys| JWKSEndpoint
    ProtectedAPI --> JWTValidator
    AdminAPI --> JWTValidator

    AuthEndpoint --> Users
    TokenEndpoint --> OAuthClients
    TokenEndpoint --> Authorizations
```

## OAuth 2.0 Grant Types Explained

### 1. Client Credentials Flow

Best for: **Machine-to-machine** communication (backend services, scheduled jobs, microservices).

```mermaid
sequenceDiagram
    participant Service as Backend Service
    participant AuthServer as Authorization Server
    participant ResourceServer as Resource Server

    Note over Service,ResourceServer: No user involvement - service authenticates itself

    Service->>AuthServer: POST /oauth2/token<br/>grant_type=client_credentials<br/>+ Basic Auth (client_id:secret)
    AuthServer->>AuthServer: Validate client credentials
    AuthServer-->>Service: Access Token (JWT)

    Service->>ResourceServer: GET /api/data<br/>Authorization: Bearer {token}
    ResourceServer->>ResourceServer: Validate JWT signature<br/>Check scopes
    ResourceServer-->>Service: Protected Resource
```

### 2. Authorization Code Flow

Best for: **Web applications** with a server-side backend that can securely store client secrets.

```mermaid
sequenceDiagram
    participant User as User Browser
    participant WebApp as Web Application
    participant AuthServer as Authorization Server
    participant ResourceServer as Resource Server

    Note over User,ResourceServer: User grants permission to app

    User->>WebApp: Click "Login"
    WebApp->>User: Redirect to Authorization Server
    User->>AuthServer: GET /oauth2/authorize<br/>?response_type=code<br/>&client_id=web-client<br/>&redirect_uri=callback<br/>&scope=read write

    AuthServer->>User: Show Login Page
    User->>AuthServer: Enter credentials
    AuthServer->>AuthServer: Authenticate user
    AuthServer->>User: Show Consent Screen
    User->>AuthServer: Approve scopes

    AuthServer->>User: Redirect to callback?code=ABC123
    User->>WebApp: GET /callback?code=ABC123

    WebApp->>AuthServer: POST /oauth2/token<br/>grant_type=authorization_code<br/>code=ABC123<br/>+ Basic Auth
    AuthServer-->>WebApp: Access Token + Refresh Token

    WebApp->>ResourceServer: GET /api/user<br/>Authorization: Bearer {token}
    ResourceServer-->>WebApp: User Data
    WebApp-->>User: Display Dashboard
```

### 3. Authorization Code + PKCE Flow

Best for: **Public clients** (SPAs, mobile apps) that cannot securely store client secrets.

```mermaid
sequenceDiagram
    participant User as User Browser
    participant SPA as Single Page App
    participant AuthServer as Authorization Server

    Note over User,AuthServer: PKCE adds security without client secret

    SPA->>SPA: Generate code_verifier (random string)
    SPA->>SPA: Generate code_challenge = SHA256(verifier)

    User->>SPA: Click "Login"
    SPA->>User: Redirect to Authorization Server

    User->>AuthServer: GET /oauth2/authorize<br/>?response_type=code<br/>&client_id=spa-client<br/>&code_challenge={challenge}<br/>&code_challenge_method=S256

    AuthServer->>User: Login + Consent
    User->>AuthServer: Approve

    AuthServer->>User: Redirect with code
    User->>SPA: GET /callback?code=XYZ789

    SPA->>AuthServer: POST /oauth2/token<br/>grant_type=authorization_code<br/>code=XYZ789<br/>code_verifier={verifier}<br/>(NO client secret!)

    AuthServer->>AuthServer: Verify: SHA256(verifier) == stored challenge
    AuthServer-->>SPA: Access Token + Refresh Token
```

### 4. Refresh Token Flow

Best for: **Renewing expired access tokens** without user re-authentication.

```mermaid
sequenceDiagram
    participant App as Application
    participant AuthServer as Authorization Server
    participant ResourceServer as Resource Server

    Note over App,ResourceServer: Access token expired, use refresh token

    App->>ResourceServer: GET /api/data<br/>Authorization: Bearer {expired_token}
    ResourceServer-->>App: 401 Unauthorized (token expired)

    App->>AuthServer: POST /oauth2/token<br/>grant_type=refresh_token<br/>refresh_token={refresh_token}
    AuthServer->>AuthServer: Validate refresh token
    AuthServer-->>App: New Access Token + New Refresh Token

    App->>ResourceServer: GET /api/data<br/>Authorization: Bearer {new_token}
    ResourceServer-->>App: Protected Resource
```

## End-to-End Flow Example

```mermaid
graph LR
    subgraph Step1 [Step 1: Get Token]
        A[Client] -->|Authenticate| B[Auth Server]
        B -->|JWT Token| A
    end

    subgraph Step2 [Step 2: Access Resource]
        A -->|Bearer Token| C[Resource Server]
        C -->|Validate JWT| D{Valid?}
        D -->|Yes| E[Return Data]
        D -->|No| F[401 Unauthorized]
    end

    subgraph Step3 [Step 3: JWT Validation]
        C -->|Fetch JWKS| B
        B -->|Public Keys| C
        C -->|Verify Signature| C
    end
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

## Quick Start

Run everything with a single command:

```bash
./run.sh
```

This will:
1. Build both Spring Boot applications
2. Start PostgreSQL, Authorization Server, and Resource Server
3. Wait for all services to be healthy
4. Display connection info and test commands

### Available Commands

| Command | Description |
|---------|-------------|
| `./run.sh start` | Start all services (default) |
| `./run.sh stop` | Stop all services |
| `./run.sh restart` | Restart all services |
| `./run.sh logs` | View service logs |
| `./run.sh status` | Show service status |
| `./run.sh clean` | Stop and remove volumes |
| `./run.sh test` | Run OAuth flow tests |

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
| service-client | service-secret | Client Credentials | Service-to-service |

## Postman Collection

Import the Postman collection for easy API testing:

```
postman/OAuth2-Demo.postman_collection.json
```

The collection includes:
1. **Health Checks** - Verify services are running
2. **Client Credentials Flow** - Get token for service-to-service
3. **Authorization Code Flow** - Web app authentication
4. **Authorization Code + PKCE** - SPA/Mobile authentication
5. **Refresh Token Flow** - Renew expired tokens
6. **Protected Resources** - Access APIs with tokens
7. **Token Management** - Introspect and revoke tokens

## Testing the OAuth Flows

### 1. Client Credentials Flow

```bash
curl -X POST http://localhost:9001/oauth2/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -u "service-client:service-secret" \
  -d "grant_type=client_credentials&scope=read write admin"
```

### 2. Authorization Code Flow

**Step 1:** Open in browser:
```
http://localhost:9001/oauth2/authorize?response_type=code&client_id=web-client&redirect_uri=http://localhost:3000/callback&scope=openid profile read write
```

**Step 2:** Exchange code for token:
```bash
curl -X POST http://localhost:9001/oauth2/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -u "web-client:secret" \
  -d "grant_type=authorization_code&code=CODE_HERE&redirect_uri=http://localhost:3000/callback"
```

### 3. Access Protected Resources

```bash
TOKEN="your_access_token_here"

# Protected endpoint
curl http://localhost:8080/api/protected \
  -H "Authorization: Bearer $TOKEN"

# User info from JWT
curl http://localhost:8080/api/user \
  -H "Authorization: Bearer $TOKEN"
```

## API Endpoints

### Authorization Server (Port 9001)

| Endpoint | Description |
|----------|-------------|
| `GET /oauth2/authorize` | Authorization endpoint (user login) |
| `POST /oauth2/token` | Token endpoint (get/refresh tokens) |
| `GET /oauth2/jwks` | JSON Web Key Set for JWT validation |
| `POST /oauth2/revoke` | Revoke tokens |
| `POST /oauth2/introspect` | Token introspection |
| `GET /userinfo` | OpenID Connect user info |
| `GET /.well-known/openid-configuration` | OIDC discovery |
| `GET /login` | Login page |

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
├── docker-compose.yml              # Docker services configuration
├── run.sh                          # One-command startup script
├── pom.xml                         # Parent Maven POM
├── postman/                        # Postman collection
│   └── OAuth2-Demo.postman_collection.json
├── init-scripts/                   # Database initialization
│   └── 01-init.sql
├── authorization-server/           # OAuth 2.0 Authorization Server
│   ├── Dockerfile
│   ├── pom.xml
│   └── src/main/
│       ├── java/com/oauth/authserver/
│       │   ├── config/             # Security & OAuth config
│       │   ├── entity/             # JPA entities
│       │   ├── repository/         # Data access
│       │   └── service/            # Business logic
│       └── resources/
│           ├── application.yml
│           ├── schema.sql
│           └── templates/login.html
└── resource-server/                # OAuth 2.0 Resource Server
    ├── Dockerfile
    ├── pom.xml
    └── src/main/
        ├── java/com/oauth/resourceserver/
        │   ├── config/             # JWT validation config
        │   └── controller/         # Protected APIs
        └── resources/
            └── application.yml
```

## JWT Token Structure

Access tokens are JWTs with the following claims:

```json
{
  "sub": "user",
  "aud": "web-client",
  "scope": ["openid", "profile", "read"],
  "iss": "http://localhost:9001",
  "exp": 1768563600,
  "iat": 1768559789,
  "authorities": ["ROLE_USER"],
  "username": "user"
}
```

## Troubleshooting

### Services Not Starting
```bash
./run.sh clean
./run.sh start
```

### Token Validation Errors
- Ensure Authorization Server is running before Resource Server
- Check that issuer-uri matches: `http://localhost:9001`
- Verify token hasn't expired

### View Logs
```bash
./run.sh logs
# Or specific service:
docker logs oauth2-auth-server
docker logs oauth2-resource-server
```

## License

MIT License
