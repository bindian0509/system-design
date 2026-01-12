# API Contracts

## Overview

This document specifies the complete API contracts for the collaborative editor system, including REST APIs for document management and WebSocket protocol for real-time collaboration.

## REST API

### Base URL

```
Production: https://api.collab-editor.example.com/v1
Staging:    https://api-staging.collab-editor.example.com/v1
```

### Authentication

All REST endpoints require authentication via Bearer token:

```http
Authorization: Bearer <jwt_token>
```

JWT claims:
```json
{
  "sub": "user_123",
  "name": "John Doe",
  "email": "john@example.com",
  "org_id": "org_456",
  "permissions": ["read", "write"],
  "exp": 1699900000
}
```

### Document Management

#### Create Document

```http
POST /documents
Content-Type: application/json
```

**Request**:
```json
{
  "title": "My Document",
  "template_id": "blank",
  "permissions": {
    "default": "viewer",
    "users": {
      "user_123": "editor",
      "user_456": "commenter"
    },
    "public": false
  }
}
```

**Response** (201 Created):
```json
{
  "id": "doc_abc123",
  "title": "My Document",
  "created_at": "2024-01-15T10:30:00Z",
  "created_by": "user_123",
  "version": 0,
  "permissions": {
    "default": "viewer",
    "users": {
      "user_123": "editor",
      "user_456": "commenter"
    },
    "public": false
  },
  "urls": {
    "edit": "https://app.example.com/doc/doc_abc123",
    "websocket": "wss://ws.example.com/doc/doc_abc123"
  }
}
```

**Errors**:
- `400 Bad Request`: Invalid input
- `401 Unauthorized`: Missing or invalid token
- `403 Forbidden`: User cannot create documents
- `429 Too Many Requests`: Rate limited

#### Get Document

```http
GET /documents/{document_id}
```

**Response** (200 OK):
```json
{
  "id": "doc_abc123",
  "title": "My Document",
  "created_at": "2024-01-15T10:30:00Z",
  "created_by": "user_123",
  "updated_at": "2024-01-15T11:45:00Z",
  "version": 42,
  "word_count": 1250,
  "character_count": 7500,
  "permissions": {
    "current_user": "editor"
  },
  "collaborators": [
    {
      "user_id": "user_123",
      "name": "John Doe",
      "avatar": "https://...",
      "is_online": true
    }
  ]
}
```

#### Get Document Snapshot

For viewers who don't need real-time sync:

```http
GET /documents/{document_id}/snapshot
Accept: application/json
```

**Response** (200 OK):
```json
{
  "document_id": "doc_abc123",
  "version": 42,
  "content": {
    "type": "doc",
    "content": [
      {
        "type": "paragraph",
        "content": [
          { "type": "text", "text": "Hello " },
          { "type": "text", "text": "world", "marks": [{ "type": "bold" }] }
        ]
      }
    ]
  },
  "snapshot_at": "2024-01-15T11:45:00Z"
}
```

**Binary format** (more efficient):
```http
GET /documents/{document_id}/snapshot
Accept: application/octet-stream
```

Returns raw CRDT snapshot binary.

#### Update Document Metadata

```http
PATCH /documents/{document_id}
Content-Type: application/json
```

**Request**:
```json
{
  "title": "New Title",
  "permissions": {
    "public": true
  }
}
```

**Response** (200 OK):
```json
{
  "id": "doc_abc123",
  "title": "New Title",
  "updated_at": "2024-01-15T12:00:00Z"
}
```

#### Delete Document

```http
DELETE /documents/{document_id}
```

**Response** (204 No Content)

Soft delete by default. Document recoverable for 30 days.

#### List Documents

```http
GET /documents?page=1&limit=20&sort=updated_at&order=desc
```

**Response** (200 OK):
```json
{
  "documents": [
    {
      "id": "doc_abc123",
      "title": "My Document",
      "updated_at": "2024-01-15T11:45:00Z",
      "word_count": 1250,
      "thumbnail": "https://..."
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 150,
    "has_more": true
  }
}
```

### Version History

#### List Versions

```http
GET /documents/{document_id}/versions?limit=50
```

**Response**:
```json
{
  "versions": [
    {
      "version": 42,
      "created_at": "2024-01-15T11:45:00Z",
      "created_by": "user_123",
      "snapshot_available": true,
      "changes_summary": "Added 250 characters"
    },
    {
      "version": 41,
      "created_at": "2024-01-15T11:30:00Z",
      "created_by": "user_456"
    }
  ]
}
```

#### Restore Version

```http
POST /documents/{document_id}/restore
Content-Type: application/json
```

**Request**:
```json
{
  "target_version": 35
}
```

**Response** (200 OK):
```json
{
  "document_id": "doc_abc123",
  "restored_to_version": 35,
  "new_version": 43,
  "message": "Document restored to version 35"
}
```

### Comments API

#### Add Comment

```http
POST /documents/{document_id}/comments
Content-Type: application/json
```

**Request**:
```json
{
  "range": {
    "start": { "block_id": "p1", "offset": 10 },
    "end": { "block_id": "p1", "offset": 25 }
  },
  "content": "This needs revision"
}
```

**Response** (201 Created):
```json
{
  "id": "comment_xyz",
  "document_id": "doc_abc123",
  "author": {
    "user_id": "user_123",
    "name": "John Doe"
  },
  "range": { ... },
  "content": "This needs revision",
  "created_at": "2024-01-15T12:00:00Z",
  "resolved": false
}
```

#### List Comments

```http
GET /documents/{document_id}/comments?resolved=false
```

#### Resolve Comment

```http
POST /documents/{document_id}/comments/{comment_id}/resolve
```

---

## WebSocket Protocol

### Connection

```
URL: wss://ws.example.com/documents/{document_id}
Headers:
  Authorization: Bearer <jwt_token>
  X-Client-ID: <uuid>
  X-Protocol-Version: 1
```

### Message Format

All messages are JSON with this envelope:

```typescript
interface Message {
  type: MessageType;
  id?: string;          // For request-response correlation
  timestamp?: number;   // Client timestamp
  payload: any;
}
```

### Client → Server Messages

#### sync_request

Request missing operations on connect/reconnect.

```json
{
  "type": "sync_request",
  "id": "req_001",
  "payload": {
    "document_id": "doc_abc123",
    "state_vector": {
      "1": 42,
      "2": 17
    },
    "resume_token": null
  }
}
```

#### operations

Send local operations to server.

```json
{
  "type": "operations",
  "id": "req_002",
  "timestamp": 1699900000000,
  "payload": {
    "document_id": "doc_abc123",
    "client_seq": 5,
    "operations": [
      {
        "type": "text_insert",
        "id": { "client": 1, "clock": 43 },
        "parent": ["content", 0],
        "origin": { "client": 1, "clock": 42 },
        "right_origin": null,
        "content": "Hello",
        "marks": []
      },
      {
        "type": "text_insert",
        "id": { "client": 1, "clock": 44 },
        "parent": ["content", 0],
        "origin": { "client": 1, "clock": 43 },
        "right_origin": null,
        "content": " ",
        "marks": []
      }
    ]
  }
}
```

#### presence

Update cursor/selection.

```json
{
  "type": "presence",
  "payload": {
    "document_id": "doc_abc123",
    "cursor": {
      "block_id": "p1",
      "offset": 42
    },
    "selection": null,
    "is_typing": true
  }
}
```

#### ping

Keepalive message.

```json
{
  "type": "ping"
}
```

### Server → Client Messages

#### connected

Sent after successful connection.

```json
{
  "type": "connected",
  "payload": {
    "client_id": 42,
    "server_time": 1699900000000,
    "protocol_version": 1,
    "features": ["binary_encoding", "presence_v2"]
  }
}
```

#### sync_response

Response to sync_request.

```json
{
  "type": "sync_response",
  "id": "req_001",
  "payload": {
    "operations": [
      {
        "type": "text_insert",
        "id": { "client": 2, "clock": 18 },
        "parent": ["content", 0],
        "origin": { "client": 2, "clock": 17 },
        "right_origin": null,
        "content": "World",
        "marks": []
      }
    ],
    "server_vector": {
      "1": 42,
      "2": 18
    },
    "has_more": false,
    "resume_token": null
  }
}
```

#### remote_ops

Broadcast of operations from other clients.

```json
{
  "type": "remote_ops",
  "payload": {
    "document_id": "doc_abc123",
    "origin": 2,
    "operations": [
      {
        "type": "text_insert",
        "id": { "client": 2, "clock": 19 },
        "parent": ["content", 0],
        "origin": { "client": 2, "clock": 18 },
        "content": "!",
        "marks": []
      }
    ],
    "server_vector": {
      "1": 44,
      "2": 19
    }
  }
}
```

#### ack

Acknowledgment of client operations.

```json
{
  "type": "ack",
  "payload": {
    "document_id": "doc_abc123",
    "client_seq": 5,
    "server_vector": {
      "1": 44,
      "2": 19
    },
    "persisted_at": 1699900001000
  }
}
```

#### presence_update

Broadcast of user presence.

```json
{
  "type": "presence_update",
  "payload": {
    "document_id": "doc_abc123",
    "presences": [
      {
        "user_id": "user_123",
        "name": "John Doe",
        "color": "#F44336",
        "cursor": { "block_id": "p1", "offset": 42 },
        "selection": null,
        "is_typing": true,
        "last_seen": 1699900001000
      },
      {
        "user_id": "user_456",
        "name": "Jane Smith",
        "color": "#2196F3",
        "cursor": { "block_id": "p2", "offset": 10 },
        "is_typing": false,
        "last_seen": 1699900000500
      }
    ]
  }
}
```

#### pong

Response to ping.

```json
{
  "type": "pong"
}
```

#### error

Error message.

```json
{
  "type": "error",
  "id": "req_002",
  "payload": {
    "code": 4009,
    "message": "Version mismatch, please resync",
    "retryable": true,
    "retry_after": null
  }
}
```

#### snapshot_available

Notification that a new snapshot is ready.

```json
{
  "type": "snapshot_available",
  "payload": {
    "document_id": "doc_abc123",
    "version": 50,
    "state_vector": {
      "1": 44,
      "2": 25
    }
  }
}
```

#### reconnect_required

Server requests client reconnect (graceful shutdown).

```json
{
  "type": "reconnect_required",
  "payload": {
    "reason": "server_shutdown",
    "delay_ms": 5000
  }
}
```

---

## Operation Types

### Text Operations

#### text_insert

```json
{
  "type": "text_insert",
  "id": { "client": 1, "clock": 43 },
  "parent": ["content", 0, "text"],
  "origin": { "client": 1, "clock": 42 },
  "right_origin": null,
  "content": "Hello",
  "marks": [
    { "type": "bold" }
  ]
}
```

#### text_delete

```json
{
  "type": "text_delete",
  "id": { "client": 1, "clock": 45 },
  "parent": ["content", 0, "text"],
  "target": { "client": 1, "clock": 43 }
}
```

### Mark Operations

#### mark_add

```json
{
  "type": "mark_add",
  "id": { "client": 1, "clock": 46 },
  "parent": ["content", 0, "text"],
  "start": { "client": 1, "clock": 40 },
  "end": { "client": 1, "clock": 44 },
  "mark": {
    "type": "link",
    "attrs": { "href": "https://example.com" }
  }
}
```

#### mark_remove

```json
{
  "type": "mark_remove",
  "id": { "client": 1, "clock": 47 },
  "parent": ["content", 0, "text"],
  "start": { "client": 1, "clock": 40 },
  "end": { "client": 1, "clock": 44 },
  "mark_type": "bold"
}
```

### Block Operations

#### block_insert

```json
{
  "type": "block_insert",
  "id": { "client": 1, "clock": 48 },
  "parent": ["content"],
  "origin": { "client": 1, "clock": 30 },
  "right_origin": null,
  "block": {
    "type": "paragraph",
    "attrs": {},
    "content": []
  }
}
```

#### block_delete

```json
{
  "type": "block_delete",
  "id": { "client": 1, "clock": 49 },
  "parent": ["content"],
  "target": { "client": 1, "clock": 48 }
}
```

#### block_update

```json
{
  "type": "block_update",
  "id": { "client": 1, "clock": 50 },
  "parent": ["content"],
  "target": { "client": 1, "clock": 30 },
  "attrs": {
    "type": "heading",
    "level": 2
  }
}
```

---

## Error Codes

### Connection Errors (4xxx)

| Code | Name | Description |
|------|------|-------------|
| 4001 | UNAUTHORIZED | Invalid or expired token |
| 4003 | FORBIDDEN | User lacks permission |
| 4004 | NOT_FOUND | Document not found |
| 4008 | TIMEOUT | Request timed out |
| 4009 | VERSION_MISMATCH | State vectors conflict |
| 4029 | RATE_LIMITED | Too many requests |

### Server Errors (5xxx)

| Code | Name | Description |
|------|------|-------------|
| 5000 | INTERNAL_ERROR | Unexpected server error |
| 5003 | UNAVAILABLE | Service temporarily unavailable |
| 5004 | STORAGE_ERROR | Storage system failure |

### Sync Errors (41xx)

| Code | Name | Description |
|------|------|-------------|
| 4100 | SYNC_CONFLICT | Unresolvable sync conflict |
| 4101 | SNAPSHOT_REQUIRED | Client must load new snapshot |
| 4102 | INVALID_OPERATION | Operation failed validation |

---

## Rate Limits

| Endpoint/Action | Limit | Window |
|-----------------|-------|--------|
| REST API (general) | 1000 req | 1 minute |
| Document creation | 100 docs | 1 hour |
| WebSocket operations | 100 ops | 1 second |
| Presence updates | 10 updates | 1 second |

Rate limit headers:
```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1699900060
```

---

## Versioning

### API Version

Current version: `v1`

Version is included in URL path:
```
/v1/documents
```

### Protocol Version

WebSocket protocol version negotiated on connect:
```
X-Protocol-Version: 1
```

Backward compatibility maintained for 2 major versions.

### Deprecation Policy

1. Announce deprecation 6 months before removal
2. Add `Deprecation` header to deprecated endpoints
3. Document migration path
4. Remove after deprecation period
