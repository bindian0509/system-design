# JWT Authentication - Spring Boot

A simple JWT-based authentication system with access tokens and refresh tokens using Spring Boot, Spring Security, and MySQL.

## Quick Start

```bash
# Start everything (MySQL + App)
docker-compose up -d --build

# View logs
docker-compose logs -f app
```

The app will be available at **http://localhost:8080**

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/register` | POST | Register new user |
| `/api/auth/login` | POST | Login and get tokens |
| `/api/auth/refresh` | POST | Refresh access token |
| `/api/auth/logout` | POST | Invalidate refresh token |

## Test

```bash
# Register
curl -X POST http://localhost:8080/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123"}'

# Login
curl -X POST http://localhost:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123"}'
```

## Postman Collection

Import the collection to test all endpoints:

```
postman/JWT_Auth_Collection.postman_collection.json
```

The collection includes:
- Auto-saving tokens to variables after login/register
- All auth endpoints (register, login, refresh, logout)
- Protected endpoint test
- Error case tests

## Documentation

See [docs/README.md](docs/README.md) for detailed documentation including architecture diagrams, token flows, and configuration options.

## Tech Stack

- Spring Boot 3.2.x
- Spring Security
- Spring Data JPA
- MySQL 8.0
- jjwt (JWT library)
- Lombok
