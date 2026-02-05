# API Contracts

## Overview

RESTful API design following OpenAPI 3.0 specifications. All endpoints use JSON for request/response bodies and support gzip compression.

## Base URL

```
Production: https://api.flights.example.com/v1
Staging:    https://api-staging.flights.example.com/v1
```

## Authentication

All authenticated endpoints require a Bearer token in the Authorization header:

```
Authorization: Bearer <jwt_token>
```

Partner APIs use API keys:

```
X-API-Key: <partner_api_key>
```

---

## 1. Flight Search Endpoints

### 1.1 Simple Search

Search for flights between two airports.

```http
GET /flights/search
```

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| origin | string | Yes | Origin airport code (IATA) |
| destination | string | Yes | Destination airport code (IATA) |
| departure_date | string | Yes | Departure date (YYYY-MM-DD) |
| return_date | string | No | Return date for round trips |
| adults | integer | No | Number of adults (default: 1) |
| children | integer | No | Number of children (default: 0) |
| infants | integer | No | Number of infants (default: 0) |
| cabin_class | string | No | economy, premium_economy, business, first |
| direct_only | boolean | No | Only show non-stop flights |
| max_stops | integer | No | Maximum number of stops (0, 1, 2) |
| sort_by | string | No | price, duration, departure_time, arrival_time |
| carriers | string[] | No | Filter by airline codes (comma-separated) |
| max_price | integer | No | Maximum price in cents |

**Example Request:**

```http
GET /flights/search?origin=JFK&destination=LAX&departure_date=2024-06-15&adults=2&cabin_class=economy
```

**Response:** `200 OK`

```json
{
  "search_id": "srch_abc123def456",
  "origin": "JFK",
  "destination": "LAX",
  "departure_date": "2024-06-15",
  "results": [
    {
      "flight_id": "flt_ua123_20240615",
      "itinerary": {
        "total_duration_minutes": 330,
        "segments": [
          {
            "segment_id": "seg_001",
            "flight_number": "UA123",
            "carrier": {
              "code": "UA",
              "name": "United Airlines",
              "logo_url": "https://cdn.example.com/airlines/ua.png"
            },
            "origin": {
              "code": "JFK",
              "name": "John F. Kennedy International Airport",
              "city": "New York",
              "terminal": "7"
            },
            "destination": {
              "code": "LAX",
              "name": "Los Angeles International Airport",
              "city": "Los Angeles",
              "terminal": "7"
            },
            "departure": {
              "time": "2024-06-15T08:00:00-04:00",
              "local_time": "08:00"
            },
            "arrival": {
              "time": "2024-06-15T11:30:00-07:00",
              "local_time": "11:30"
            },
            "duration_minutes": 330,
            "aircraft": {
              "code": "738",
              "name": "Boeing 737-800"
            },
            "cabin_class": "economy",
            "fare_class": "Y"
          }
        ]
      },
      "pricing": {
        "total_cents": 59800,
        "price_per_adult_cents": 29900,
        "taxes_cents": 9000,
        "fees_cents": 0,
        "currency": "USD",
        "fare_breakdown": [
          {
            "passenger_type": "adult",
            "quantity": 2,
            "base_fare_cents": 25400,
            "taxes_cents": 4500
          }
        ]
      },
      "availability": {
        "seats_remaining": 7,
        "fare_class": "Y",
        "refundable": false,
        "changeable": true,
        "change_fee_cents": 20000
      },
      "baggage": {
        "carry_on": {
          "included": true,
          "quantity": 1,
          "weight_kg": 10
        },
        "checked": {
          "included": 0,
          "first_bag_cents": 3500,
          "second_bag_cents": 4500
        }
      },
      "amenities": ["wifi", "power_outlet", "entertainment"],
      "supplier": {
        "code": "amadeus",
        "booking_class": "Y"
      },
      "deep_link": "https://book.example.com/flights/flt_ua123_20240615"
    }
  ],
  "filters": {
    "price_range": {
      "min_cents": 29900,
      "max_cents": 89900
    },
    "duration_range": {
      "min_minutes": 320,
      "max_minutes": 480
    },
    "available_carriers": ["UA", "AA", "DL", "B6"],
    "available_stops": [0, 1, 2]
  },
  "metadata": {
    "total_results": 145,
    "search_time_ms": 1250,
    "cache_hit": false,
    "suppliers_queried": ["amadeus", "sabre", "direct_ua"]
  }
}
```

### 1.2 Multi-City Search

Search for complex multi-leg itineraries.

```http
POST /flights/search
```

**Request Body:**

```json
{
  "legs": [
    {
      "origin": "JFK",
      "destination": "LAX",
      "departure_date": "2024-06-15"
    },
    {
      "origin": "LAX",
      "destination": "ORD",
      "departure_date": "2024-06-20"
    },
    {
      "origin": "ORD",
      "destination": "JFK",
      "departure_date": "2024-06-25"
    }
  ],
  "passengers": {
    "adults": 1,
    "children": 0,
    "infants": 0
  },
  "cabin_class": "economy",
  "preferences": {
    "direct_only": false,
    "max_stops": 1
  }
}
```

**Response:** `200 OK`

```json
{
  "search_id": "srch_multi_xyz789",
  "results": [
    {
      "itinerary_id": "itin_001",
      "legs": [
        {
          "leg_index": 0,
          "segments": [/* segment objects */]
        },
        {
          "leg_index": 1,
          "segments": [/* segment objects */]
        },
        {
          "leg_index": 2,
          "segments": [/* segment objects */]
        }
      ],
      "total_pricing": {
        "total_cents": 89700,
        "currency": "USD"
      }
    }
  ]
}
```

### 1.3 Streaming Search (SSE)

Get progressive results via Server-Sent Events.

```http
GET /flights/search/{search_id}/stream
```

**Headers:**

```
Accept: text/event-stream
```

**Response:** Server-Sent Events stream

```
event: batch
data: {"batch_number": 1, "results": [...], "is_final": false}

event: batch
data: {"batch_number": 2, "results": [...], "is_final": false}

event: complete
data: {"total_results": 145, "search_time_ms": 2100}
```

---

## 2. Price Endpoints

### 2.1 Real-Time Price Verification

Verify current price before booking.

```http
GET /flights/{flight_id}/price
```

**Response:** `200 OK`

```json
{
  "flight_id": "flt_ua123_20240615",
  "pricing": {
    "total_cents": 29900,
    "taxes_cents": 4500,
    "currency": "USD"
  },
  "availability": {
    "seats_remaining": 5,
    "fare_class": "Y",
    "is_available": true
  },
  "price_changed": false,
  "previous_price_cents": null,
  "verified_at": "2024-06-10T14:30:00Z",
  "valid_until": "2024-06-10T14:45:00Z"
}
```

### 2.2 Historical Price Data

Get historical prices for a route.

```http
GET /routes/{route_id}/history
```

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| days | integer | No | Number of days of history (default: 30, max: 90) |
| departure_date | string | No | Specific departure date to track |

**Response:** `200 OK`

```json
{
  "route_id": "JFK-LAX",
  "departure_date": "2024-07-01",
  "history": [
    {
      "date": "2024-06-01",
      "lowest_price_cents": 34900,
      "average_price_cents": 45200,
      "highest_price_cents": 89900
    },
    {
      "date": "2024-06-02",
      "lowest_price_cents": 32900,
      "average_price_cents": 43500,
      "highest_price_cents": 85000
    }
  ],
  "statistics": {
    "current_lowest_cents": 29900,
    "period_average_cents": 44300,
    "period_low_cents": 27500,
    "period_high_cents": 95000,
    "price_trend": "decreasing",
    "percentile_current": 25
  }
}
```

### 2.3 Price Prediction

Get ML-powered price prediction.

```http
GET /routes/{route_id}/predict
```

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| departure_date | string | Yes | Target departure date |

**Response:** `200 OK`

```json
{
  "route_id": "JFK-LAX",
  "departure_date": "2024-07-01",
  "current_price_cents": 29900,
  "prediction": {
    "direction": "increase",
    "confidence": 0.78,
    "predicted_change_percent": 12.5,
    "predicted_price_cents": 33640,
    "time_horizon_days": 7
  },
  "recommendation": {
    "action": "book_now",
    "message": "Prices are likely to rise by 12% in the next week. Book now for best value.",
    "urgency": "high"
  },
  "factors": [
    {
      "factor": "high_demand",
      "impact": "positive",
      "description": "Search volume for this route is 40% above average"
    },
    {
      "factor": "approaching_departure",
      "impact": "positive",
      "description": "Only 21 days until departure"
    },
    {
      "factor": "limited_seats",
      "impact": "positive",
      "description": "Less than 10 seats remaining on most flights"
    }
  ],
  "model_version": "v2.3.1",
  "generated_at": "2024-06-10T14:30:00Z"
}
```

---

## 3. Alert Endpoints

### 3.1 Create Price Alert

```http
POST /alerts
```

**Request Body:**

```json
{
  "origin": "JFK",
  "destination": "LAX",
  "departure_date": "2024-07-01",
  "return_date": "2024-07-08",
  "target_price_cents": 25000,
  "notification_channels": ["email", "push"],
  "passengers": {
    "adults": 1
  }
}
```

**Response:** `201 Created`

```json
{
  "alert_id": "alt_abc123",
  "status": "active",
  "origin": "JFK",
  "destination": "LAX",
  "departure_date": "2024-07-01",
  "return_date": "2024-07-08",
  "target_price_cents": 25000,
  "current_lowest_cents": 29900,
  "notification_channels": ["email", "push"],
  "created_at": "2024-06-10T14:30:00Z"
}
```

### 3.2 List User Alerts

```http
GET /alerts
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| status | string | Filter by status: active, triggered, expired |
| page | integer | Page number (default: 1) |
| limit | integer | Results per page (default: 20, max: 100) |

**Response:** `200 OK`

```json
{
  "alerts": [
    {
      "alert_id": "alt_abc123",
      "status": "active",
      "origin": "JFK",
      "destination": "LAX",
      "departure_date": "2024-07-01",
      "target_price_cents": 25000,
      "current_lowest_cents": 29900,
      "created_at": "2024-06-10T14:30:00Z",
      "last_checked_at": "2024-06-10T15:00:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 5,
    "has_more": false
  }
}
```

### 3.3 Delete Alert

```http
DELETE /alerts/{alert_id}
```

**Response:** `204 No Content`

---

## 4. Booking Endpoints

### 4.1 Verify Availability & Price

Pre-booking verification step.

```http
POST /bookings/verify
```

**Request Body:**

```json
{
  "flight_id": "flt_ua123_20240615",
  "passengers": [
    {
      "type": "adult",
      "first_name": "John",
      "last_name": "Doe",
      "date_of_birth": "1985-03-15",
      "gender": "male"
    }
  ]
}
```

**Response:** `200 OK`

```json
{
  "verification_id": "ver_xyz789",
  "flight_id": "flt_ua123_20240615",
  "is_available": true,
  "pricing": {
    "total_cents": 29900,
    "taxes_cents": 4500,
    "fees_cents": 0,
    "currency": "USD"
  },
  "price_changed": false,
  "valid_until": "2024-06-10T15:00:00Z",
  "required_fields": {
    "passport": false,
    "known_traveler_number": false
  }
}
```

### 4.2 Create Booking

```http
POST /bookings
```

**Request Body:**

```json
{
  "verification_id": "ver_xyz789",
  "passengers": [
    {
      "type": "adult",
      "first_name": "John",
      "last_name": "Doe",
      "date_of_birth": "1985-03-15",
      "gender": "male",
      "email": "john.doe@example.com",
      "phone": "+1-555-123-4567"
    }
  ],
  "contact": {
    "email": "john.doe@example.com",
    "phone": "+1-555-123-4567"
  },
  "payment": {
    "method": "card",
    "token": "tok_stripe_abc123"
  },
  "idempotency_key": "idem_user123_20240610_001"
}
```

**Response:** `201 Created`

```json
{
  "booking_id": "bkg_def456",
  "booking_reference": "ABC123",
  "status": "confirmed",
  "itinerary": {
    "segments": [
      {
        "flight_number": "UA123",
        "carrier": "United Airlines",
        "origin": "JFK",
        "destination": "LAX",
        "departure": "2024-06-15T08:00:00-04:00",
        "arrival": "2024-06-15T11:30:00-07:00"
      }
    ]
  },
  "passengers": [
    {
      "first_name": "John",
      "last_name": "Doe",
      "ticket_number": "0161234567890"
    }
  ],
  "pricing": {
    "total_cents": 29900,
    "currency": "USD"
  },
  "payment": {
    "status": "charged",
    "last_four": "4242"
  },
  "supplier_confirmation": "AMADEUS-XYZ789",
  "created_at": "2024-06-10T14:35:00Z"
}
```

### 4.3 Get Booking Details

```http
GET /bookings/{booking_id}
```

**Response:** `200 OK`

```json
{
  "booking_id": "bkg_def456",
  "booking_reference": "ABC123",
  "status": "confirmed",
  "itinerary": {/* ... */},
  "passengers": [/* ... */],
  "pricing": {/* ... */},
  "payment": {
    "status": "charged",
    "method": "card",
    "last_four": "4242",
    "charged_at": "2024-06-10T14:35:00Z"
  },
  "check_in": {
    "available_at": "2024-06-14T08:00:00Z",
    "check_in_url": "https://www.united.com/checkin"
  },
  "cancellation_policy": {
    "refundable": false,
    "cancel_by": "2024-06-14T08:00:00Z",
    "penalty_cents": 20000
  },
  "created_at": "2024-06-10T14:35:00Z",
  "updated_at": "2024-06-10T14:35:00Z"
}
```

---

## 5. Reference Data Endpoints

### 5.1 Airport Autocomplete

```http
GET /airports/search?q=new+york
```

**Response:** `200 OK`

```json
{
  "results": [
    {
      "code": "JFK",
      "name": "John F. Kennedy International Airport",
      "city": "New York",
      "country": "United States",
      "country_code": "US",
      "type": "airport"
    },
    {
      "code": "NYC",
      "name": "New York (All Airports)",
      "city": "New York",
      "country": "United States",
      "country_code": "US",
      "type": "city"
    },
    {
      "code": "LGA",
      "name": "LaGuardia Airport",
      "city": "New York",
      "country": "United States",
      "country_code": "US",
      "type": "airport"
    }
  ]
}
```

### 5.2 Airline Information

```http
GET /airlines/{carrier_code}
```

**Response:** `200 OK`

```json
{
  "code": "UA",
  "name": "United Airlines",
  "logo_url": "https://cdn.example.com/airlines/ua.png",
  "alliance": "Star Alliance",
  "baggage_policy_url": "https://www.united.com/baggage"
}
```

---

## Error Responses

All errors follow a consistent format:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid departure date format",
    "details": [
      {
        "field": "departure_date",
        "message": "Must be in YYYY-MM-DD format"
      }
    ],
    "request_id": "req_abc123"
  }
}
```

### Error Codes

| HTTP Status | Error Code | Description |
|-------------|------------|-------------|
| 400 | VALIDATION_ERROR | Invalid request parameters |
| 401 | UNAUTHORIZED | Missing or invalid authentication |
| 403 | FORBIDDEN | Insufficient permissions |
| 404 | NOT_FOUND | Resource not found |
| 409 | CONFLICT | Resource conflict (e.g., duplicate booking) |
| 422 | UNPROCESSABLE_ENTITY | Semantic error (e.g., past departure date) |
| 429 | RATE_LIMITED | Too many requests |
| 500 | INTERNAL_ERROR | Server error |
| 502 | SUPPLIER_ERROR | Upstream supplier failure |
| 503 | SERVICE_UNAVAILABLE | Service temporarily unavailable |

---

## Rate Limits

| Tier | Limit | Scope |
|------|-------|-------|
| Anonymous | 20/minute | IP address |
| Free User | 100/minute | User ID |
| Premium User | 500/minute | User ID |
| Partner API | 1000/minute | API Key |

Rate limit headers are included in all responses:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1623456789
```

---

## Webhooks (Partner API)

Partners can register webhooks for real-time notifications.

### Webhook Events

| Event | Description |
|-------|-------------|
| `booking.created` | New booking created |
| `booking.confirmed` | Booking confirmed by supplier |
| `booking.cancelled` | Booking cancelled |
| `price.dropped` | Price dropped for monitored route |
| `flight.changed` | Flight schedule changed |

### Webhook Payload

```json
{
  "event_type": "booking.confirmed",
  "event_id": "evt_abc123",
  "timestamp": "2024-06-10T14:35:00Z",
  "data": {
    "booking_id": "bkg_def456",
    "booking_reference": "ABC123"
  }
}
```

### Webhook Security

All webhooks include a signature header for verification:

```
X-Webhook-Signature: sha256=abc123...
```
