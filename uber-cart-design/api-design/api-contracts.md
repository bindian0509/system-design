# Uber Cart System - API Contracts

## Overview

This document defines the REST and GraphQL API contracts for the Uber Cart Management System, including endpoint specifications, request/response schemas, error handling, and authentication requirements.

## API Design Principles

1. **RESTful Design**: Resources are nouns, HTTP methods are verbs
2. **Versioning**: URI-based versioning (`/api/v1/`)
3. **Pagination**: Cursor-based for large collections
4. **Idempotency**: Idempotency keys for POST/PUT operations
5. **HATEOAS**: Links for discoverability where appropriate

## Base URL

```
Production: https://api.uber.com/cart/v1
Staging:    https://api.staging.uber.com/cart/v1
```

## Authentication

All API requests require authentication via JWT Bearer token.

```http
Authorization: Bearer <access_token>
```

### Token Structure

```json
{
  "sub": "user_id",
  "aud": "uber-cart-api",
  "exp": 1234567890,
  "iat": 1234567800,
  "scope": ["cart:read", "cart:write", "orders:read", "orders:write"],
  "sub_user_id": "optional_sub_user_id",
  "permissions": ["view_parent_orders"]
}
```

## Common Headers

### Request Headers

| Header | Required | Description |
|--------|----------|-------------|
| `Authorization` | Yes | Bearer token |
| `X-Request-ID` | Yes | Unique request identifier |
| `X-Idempotency-Key` | POST/PUT | Idempotency key for mutations |
| `X-Device-ID` | Recommended | Client device identifier |
| `Accept-Language` | No | Preferred language (default: en) |
| `X-Client-Version` | Recommended | Client app version |

### Response Headers

| Header | Description |
|--------|-------------|
| `X-Request-ID` | Echo of request ID |
| `X-RateLimit-Limit` | Rate limit ceiling |
| `X-RateLimit-Remaining` | Remaining requests |
| `X-RateLimit-Reset` | Rate limit reset timestamp |

## Error Response Format

```json
{
  "error": {
    "code": "CART_ITEM_UNAVAILABLE",
    "message": "The requested item is no longer available",
    "details": {
      "item_id": "item_123",
      "merchant_id": "merchant_456",
      "available_alternatives": ["item_789"]
    },
    "request_id": "req_abc123",
    "timestamp": "2024-01-15T10:30:00Z"
  }
}
```

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `UNAUTHORIZED` | 401 | Invalid or expired token |
| `FORBIDDEN` | 403 | Insufficient permissions |
| `CART_NOT_FOUND` | 404 | Cart does not exist |
| `ORDER_NOT_FOUND` | 404 | Order does not exist |
| `CART_EXPIRED` | 410 | Cart has expired |
| `CART_ITEM_UNAVAILABLE` | 422 | Item not available |
| `PRICE_CHANGED` | 422 | Item price has changed |
| `MERCHANT_CLOSED` | 422 | Merchant is closed |
| `VALIDATION_ERROR` | 422 | Invalid request data |
| `RATE_LIMITED` | 429 | Too many requests |
| `INTERNAL_ERROR` | 500 | Server error |

---

## Cart API

### Create Cart

Creates a new shopping cart for the authenticated user.

```http
POST /carts
```

**Request Body**

```json
{
  "session_id": "sess_abc123",
  "fulfillment_type": "DELIVERY",
  "delivery_address_id": "addr_123"
}
```

**Response (201 Created)**

```json
{
  "data": {
    "id": "cart_abc123",
    "user_id": "user_123",
    "status": "ACTIVE",
    "fulfillment_type": "DELIVERY",
    "delivery_address": {
      "id": "addr_123",
      "address_line_1": "123 Main St",
      "city": "San Francisco",
      "state": "CA",
      "postal_code": "94102"
    },
    "merchant_groups": [],
    "pricing": {
      "subtotal": { "amount": 0, "currency": "USD", "display": "$0.00" },
      "delivery_fee": { "amount": 0, "currency": "USD", "display": "$0.00" },
      "service_fee": { "amount": 0, "currency": "USD", "display": "$0.00" },
      "tax": { "amount": 0, "currency": "USD", "display": "$0.00" },
      "total": { "amount": 0, "currency": "USD", "display": "$0.00" }
    },
    "version": 1,
    "created_at": "2024-01-15T10:30:00Z",
    "expires_at": "2024-01-15T12:30:00Z"
  }
}
```

### Get Cart

Retrieves the current user's active cart.

```http
GET /carts/current
```

**Response (200 OK)**

```json
{
  "data": {
    "id": "cart_abc123",
    "user_id": "user_123",
    "status": "ACTIVE",
    "fulfillment_type": "DELIVERY",
    "delivery_address": {
      "id": "addr_123",
      "address_line_1": "123 Main St",
      "city": "San Francisco"
    },
    "merchant_groups": [
      {
        "merchant_id": "merchant_456",
        "merchant_name": "Joe's Pizza",
        "merchant_logo": "https://...",
        "merchant_rating": 4.5,
        "is_open": true,
        "estimated_prep_time": 25,
        "items": [
          {
            "id": "item_789",
            "item_id": "menu_item_123",
            "name": "Margherita Pizza",
            "description": "Classic tomato and mozzarella",
            "image_url": "https://...",
            "quantity": 2,
            "unit_price": { "amount": 1499, "currency": "USD", "display": "$14.99" },
            "total_price": { "amount": 2998, "currency": "USD", "display": "$29.98" },
            "customizations": [
              {
                "group_name": "Size",
                "selections": ["Large"],
                "additional_price": { "amount": 300, "currency": "USD", "display": "$3.00" }
              }
            ],
            "is_available": true
          }
        ],
        "subtotal": { "amount": 2998, "currency": "USD", "display": "$29.98" },
        "delivery_fee": { "amount": 399, "currency": "USD", "display": "$3.99" },
        "available_fulfillment_types": ["DELIVERY", "PICKUP"]
      }
    ],
    "pricing": {
      "subtotal": { "amount": 2998, "currency": "USD", "display": "$29.98" },
      "delivery_fee": { "amount": 399, "currency": "USD", "display": "$3.99" },
      "service_fee": { "amount": 299, "currency": "USD", "display": "$2.99" },
      "tax": { "amount": 264, "currency": "USD", "display": "$2.64" },
      "discount": { "amount": 0, "currency": "USD", "display": "$0.00" },
      "total": { "amount": 3960, "currency": "USD", "display": "$39.60" }
    },
    "applied_promo_codes": [],
    "version": 3,
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:45:00Z",
    "expires_at": "2024-01-15T12:30:00Z"
  }
}
```

### Get Cart by ID

```http
GET /carts/{cart_id}
```

### Add Item to Cart

```http
POST /carts/{cart_id}/items
```

**Request Body**

```json
{
  "item_id": "menu_item_123",
  "merchant_id": "merchant_456",
  "quantity": 2,
  "customizations": {
    "size": {
      "option_id": "size_large",
      "quantity": 1
    },
    "toppings": {
      "option_ids": ["topping_mushroom", "topping_olive"],
      "quantities": [1, 1]
    }
  },
  "special_notes": "Extra crispy please"
}
```

**Response (201 Created)**

```json
{
  "data": {
    "id": "cart_item_abc",
    "cart_id": "cart_abc123",
    "item_id": "menu_item_123",
    "merchant_id": "merchant_456",
    "name": "Margherita Pizza",
    "quantity": 2,
    "unit_price": { "amount": 1799, "currency": "USD", "display": "$17.99" },
    "total_price": { "amount": 3598, "currency": "USD", "display": "$35.98" },
    "customizations": [...],
    "special_notes": "Extra crispy please",
    "is_available": true,
    "added_at": "2024-01-15T10:45:00Z"
  },
  "cart_summary": {
    "item_count": 3,
    "total": { "amount": 5560, "currency": "USD", "display": "$55.60" },
    "version": 4
  }
}
```

### Update Cart Item

```http
PUT /carts/{cart_id}/items/{item_id}
```

**Request Body**

```json
{
  "quantity": 3,
  "customizations": {...},
  "special_notes": "Updated notes"
}
```

**Response (200 OK)**

```json
{
  "data": {
    "id": "cart_item_abc",
    "quantity": 3,
    "total_price": { "amount": 5397, "currency": "USD", "display": "$53.97" },
    "updated_at": "2024-01-15T10:50:00Z"
  },
  "cart_summary": {
    "item_count": 4,
    "total": { "amount": 7160, "currency": "USD", "display": "$71.60" },
    "version": 5
  }
}
```

### Remove Item from Cart

```http
DELETE /carts/{cart_id}/items/{item_id}
```

**Response (200 OK)**

```json
{
  "data": {
    "removed_item_id": "cart_item_abc"
  },
  "cart_summary": {
    "item_count": 2,
    "total": { "amount": 3960, "currency": "USD", "display": "$39.60" },
    "version": 6
  }
}
```

### Update Cart Settings

Update fulfillment type, delivery address, or scheduled time.

```http
PATCH /carts/{cart_id}
```

**Request Body**

```json
{
  "fulfillment_type": "PICKUP",
  "scheduled_time": "2024-01-15T18:00:00Z"
}
```

### Apply Promo Code

```http
POST /carts/{cart_id}/promo-codes
```

**Request Body**

```json
{
  "code": "SAVE20"
}
```

**Response (200 OK)**

```json
{
  "data": {
    "code": "SAVE20",
    "description": "20% off your order",
    "discount_type": "PERCENTAGE",
    "discount_value": 20,
    "applied_discount": { "amount": 792, "currency": "USD", "display": "$7.92" }
  },
  "cart_summary": {
    "total": { "amount": 3168, "currency": "USD", "display": "$31.68" },
    "version": 7
  }
}
```

### Validate Cart

Validate cart before checkout.

```http
POST /carts/{cart_id}/validate
```

**Response (200 OK) - Valid**

```json
{
  "data": {
    "is_valid": true,
    "warnings": [],
    "pricing": {...}
  }
}
```

**Response (200 OK) - Invalid**

```json
{
  "data": {
    "is_valid": false,
    "errors": [
      {
        "type": "ITEM_UNAVAILABLE",
        "item_id": "cart_item_abc",
        "message": "Margherita Pizza is no longer available"
      },
      {
        "type": "PRICE_CHANGED",
        "item_id": "cart_item_def",
        "message": "Price has changed from $14.99 to $16.99",
        "old_price": { "amount": 1499 },
        "new_price": { "amount": 1699 }
      }
    ],
    "warnings": [
      {
        "type": "MERCHANT_CLOSING_SOON",
        "merchant_id": "merchant_456",
        "message": "Joe's Pizza closes in 30 minutes"
      }
    ]
  }
}
```

### Checkout Cart

Convert cart to order(s).

```http
POST /carts/{cart_id}/checkout
```

**Request Body**

```json
{
  "payment_method_id": "pm_abc123",
  "tip_amount": { "amount": 500, "currency": "USD" },
  "delivery_instructions": "Leave at door",
  "contact_phone": "+1-555-123-4567"
}
```

**Response (201 Created)**

```json
{
  "data": {
    "orders": [
      {
        "id": "order_xyz789",
        "order_number": "UE-1234567",
        "merchant_name": "Joe's Pizza",
        "status": "PENDING",
        "total": { "amount": 4460, "currency": "USD", "display": "$44.60" },
        "estimated_delivery_time": "2024-01-15T11:30:00Z"
      }
    ],
    "cart_id": "cart_abc123",
    "cart_status": "CHECKED_OUT"
  }
}
```

---

## Order API

### List Orders

Get orders for the authenticated user.

```http
GET /orders
```

**Query Parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string[] | Filter by status (comma-separated) |
| `fulfillment_type` | string | Filter by fulfillment type |
| `from_date` | ISO8601 | Filter orders from this date |
| `to_date` | ISO8601 | Filter orders until this date |
| `merchant_id` | string | Filter by merchant |
| `limit` | integer | Page size (default: 20, max: 100) |
| `cursor` | string | Pagination cursor |

**Response (200 OK)**

```json
{
  "data": {
    "orders": [
      {
        "id": "order_xyz789",
        "order_number": "UE-1234567",
        "status": "IN_TRANSIT",
        "fulfillment_type": "DELIVERY",
        "merchant": {
          "id": "merchant_456",
          "name": "Joe's Pizza",
          "logo": "https://..."
        },
        "items_summary": "Margherita Pizza, Garlic Bread",
        "item_count": 3,
        "total": { "amount": 4460, "currency": "USD", "display": "$44.60" },
        "estimated_delivery_time": "2024-01-15T11:30:00Z",
        "created_at": "2024-01-15T10:50:00Z"
      }
    ],
    "pagination": {
      "has_more": true,
      "next_cursor": "cursor_abc123"
    }
  }
}
```

### Get Order Details

```http
GET /orders/{order_id}
```

**Response (200 OK)**

```json
{
  "data": {
    "id": "order_xyz789",
    "order_number": "UE-1234567",
    "status": "IN_TRANSIT",
    "status_history": [
      { "status": "PENDING", "timestamp": "2024-01-15T10:50:00Z" },
      { "status": "CONFIRMED", "timestamp": "2024-01-15T10:51:00Z" },
      { "status": "PREPARING", "timestamp": "2024-01-15T10:52:00Z" },
      { "status": "DRIVER_ASSIGNED", "timestamp": "2024-01-15T11:05:00Z" },
      { "status": "IN_TRANSIT", "timestamp": "2024-01-15T11:15:00Z" }
    ],
    "fulfillment_type": "DELIVERY",
    "fulfillment": {
      "type": "DELIVERY",
      "status": "IN_TRANSIT",
      "driver": {
        "name": "John D.",
        "photo": "https://...",
        "rating": 4.9,
        "vehicle": {
          "type": "Car",
          "description": "Silver Toyota Camry",
          "license_plate": "ABC123"
        },
        "current_location": {
          "latitude": 37.7749,
          "longitude": -122.4194
        }
      },
      "tracking_url": "https://...",
      "estimated_arrival": "2024-01-15T11:25:00Z"
    },
    "merchant": {
      "id": "merchant_456",
      "name": "Joe's Pizza",
      "logo": "https://...",
      "phone": "+1-555-987-6543"
    },
    "items": [
      {
        "id": "order_item_1",
        "name": "Margherita Pizza",
        "quantity": 2,
        "unit_price": { "amount": 1499, "currency": "USD", "display": "$14.99" },
        "total_price": { "amount": 2998, "currency": "USD", "display": "$29.98" },
        "customizations": [
          { "group_name": "Size", "selections": ["Large"] }
        ],
        "status": "PREPARED"
      }
    ],
    "delivery_address": {
      "address_line_1": "123 Main St",
      "city": "San Francisco",
      "state": "CA",
      "postal_code": "94102",
      "delivery_instructions": "Leave at door"
    },
    "pricing": {
      "subtotal": { "amount": 2998, "currency": "USD", "display": "$29.98" },
      "delivery_fee": { "amount": 399, "currency": "USD", "display": "$3.99" },
      "service_fee": { "amount": 299, "currency": "USD", "display": "$2.99" },
      "tax": { "amount": 264, "currency": "USD", "display": "$2.64" },
      "tip": { "amount": 500, "currency": "USD", "display": "$5.00" },
      "discount": { "amount": 0, "currency": "USD", "display": "$0.00" },
      "total": { "amount": 4460, "currency": "USD", "display": "$44.60" }
    },
    "can_cancel": false,
    "can_modify": false,
    "modification_deadline": "2024-01-15T10:55:00Z",
    "created_at": "2024-01-15T10:50:00Z"
  }
}
```

### Cancel Order

```http
POST /orders/{order_id}/cancel
```

**Request Body**

```json
{
  "reason": "CHANGED_MIND",
  "additional_comments": "Ordered from wrong restaurant"
}
```

**Response (200 OK)**

```json
{
  "data": {
    "id": "order_xyz789",
    "status": "CANCELLED",
    "cancelled_at": "2024-01-15T10:52:00Z",
    "refund": {
      "id": "refund_123",
      "amount": { "amount": 4460, "currency": "USD", "display": "$44.60" },
      "status": "PROCESSING",
      "estimated_arrival": "3-5 business days"
    }
  }
}
```

### Modify Order

```http
POST /orders/{order_id}/modify
```

**Request Body**

```json
{
  "items_to_add": [
    {
      "item_id": "menu_item_456",
      "quantity": 1
    }
  ],
  "items_to_remove": ["order_item_2"],
  "items_to_update": [
    {
      "item_id": "order_item_1",
      "quantity": 3
    }
  ],
  "special_notes": "Updated delivery notes"
}
```

**Response (200 OK)**

```json
{
  "data": {
    "id": "order_xyz789",
    "status": "PREPARING",
    "modification_status": "APPLIED",
    "items": [...],
    "pricing": {
      "previous_total": { "amount": 4460 },
      "new_total": { "amount": 5560 },
      "additional_charge": { "amount": 1100 }
    }
  }
}
```

### Get Sub-User Orders

For parent users to view their sub-users' orders.

```http
GET /orders/family/{sub_user_id}
```

**Response (200 OK)**

```json
{
  "data": {
    "sub_user": {
      "id": "sub_user_123",
      "display_name": "Alex",
      "avatar_url": "https://..."
    },
    "orders": [
      {
        "id": "order_abc123",
        "order_number": "UE-9876543",
        "status": "DELIVERED",
        "merchant": { "name": "Burger Joint" },
        "total": { "amount": 2150, "currency": "USD", "display": "$21.50" },
        "created_at": "2024-01-14T12:30:00Z"
      }
    ],
    "access_level": "READ_ONLY"
  }
}
```

### Track Order (WebSocket)

Real-time order tracking via WebSocket.

```
wss://api.uber.com/cart/v1/orders/{order_id}/track
```

**Connection Message**

```json
{
  "type": "CONNECTED",
  "order_id": "order_xyz789"
}
```

**Status Update Message**

```json
{
  "type": "STATUS_UPDATE",
  "order_id": "order_xyz789",
  "status": "IN_TRANSIT",
  "timestamp": "2024-01-15T11:15:00Z"
}
```

**Location Update Message**

```json
{
  "type": "LOCATION_UPDATE",
  "order_id": "order_xyz789",
  "location": {
    "latitude": 37.7749,
    "longitude": -122.4194,
    "heading": 180,
    "speed": 25
  },
  "eta_minutes": 5,
  "timestamp": "2024-01-15T11:20:00Z"
}
```

---

## User API

### Get User Profile

```http
GET /users/me
```

### Get User Addresses

```http
GET /users/me/addresses
```

### Add Address

```http
POST /users/me/addresses
```

### Get Sub-Users

```http
GET /users/me/sub-users
```

**Response (200 OK)**

```json
{
  "data": {
    "sub_users": [
      {
        "id": "sub_user_123",
        "display_name": "Alex",
        "avatar_url": "https://...",
        "permission_level": "LIMITED",
        "status": "ACTIVE",
        "restrictions": {
          "daily_spending_limit": { "amount": 5000, "currency": "USD" },
          "per_order_limit": { "amount": 2500, "currency": "USD" }
        },
        "spending_today": { "amount": 1500, "currency": "USD" },
        "created_at": "2024-01-01T00:00:00Z"
      }
    ]
  }
}
```

### Create Sub-User

```http
POST /users/me/sub-users
```

**Request Body**

```json
{
  "first_name": "Alex",
  "last_name": "Smith",
  "email": "alex@example.com",
  "date_of_birth": "2010-05-15",
  "permission_level": "LIMITED",
  "restrictions": {
    "daily_spending_limit": { "amount": 5000, "currency": "USD" },
    "per_order_limit": { "amount": 2500, "currency": "USD" },
    "allowed_fulfillment_types": ["PICKUP"],
    "delivery_address_ids": ["addr_home"]
  }
}
```

### Update Sub-User Restrictions

```http
PATCH /users/me/sub-users/{sub_user_id}/restrictions
```

---

## Partner Orders API

For orders from third-party partners.

### List Partner Orders

```http
GET /orders?partner_id={partner_id}
```

### Get Partner Order Details

```http
GET /orders/{order_id}
```

Response includes `partner` object:

```json
{
  "data": {
    "id": "order_partner_123",
    "is_partner_order": true,
    "partner": {
      "id": "partner_abc",
      "name": "Grocery Partner",
      "logo": "https://...",
      "external_order_id": "GP-98765"
    },
    "allowed_operations": ["TRACK", "CONTACT_SUPPORT"],
    "restricted_operations": ["CANCEL", "MODIFY"],
    "restriction_reason": "Partner orders cannot be modified through Uber"
  }
}
```

---

## GraphQL API

Alternative GraphQL endpoint for flexible querying.

```
POST /graphql
```

### Schema Excerpt

```graphql
type Query {
  # Cart
  cart(id: ID!): Cart
  currentCart: Cart

  # Orders
  order(id: ID!): Order
  orders(
    status: [OrderStatus!]
    fulfillmentType: FulfillmentType
    limit: Int
    cursor: String
  ): OrderConnection!

  # Sub-user orders
  subUserOrders(subUserId: ID!): [Order!]!
}

type Mutation {
  # Cart mutations
  createCart(input: CreateCartInput!): Cart!
  addCartItem(cartId: ID!, input: CartItemInput!): CartItemResult!
  updateCartItem(cartId: ID!, itemId: ID!, input: CartItemUpdate!): CartItem!
  removeCartItem(cartId: ID!, itemId: ID!): RemoveItemResult!
  checkout(cartId: ID!, input: CheckoutInput!): CheckoutResult!

  # Order mutations
  cancelOrder(orderId: ID!, reason: String!): Order!
  modifyOrder(orderId: ID!, input: OrderModificationInput!): Order!
}

type Subscription {
  # Real-time order updates
  orderUpdated(orderId: ID!): OrderUpdate!

  # Cart sync for offline
  cartSynced(cartId: ID!): CartSyncEvent!
}

type Cart {
  id: ID!
  status: CartStatus!
  fulfillmentType: FulfillmentType
  merchantGroups: [MerchantGroup!]!
  pricing: CartPricing!
  version: Int!
  createdAt: DateTime!
  expiresAt: DateTime!
}

type Order {
  id: ID!
  orderNumber: String!
  status: OrderStatus!
  fulfillmentType: FulfillmentType!
  fulfillment: Fulfillment!
  merchant: Merchant!
  items: [OrderItem!]!
  pricing: OrderPricing!
  deliveryAddress: Address
  isPartnerOrder: Boolean!
  partner: Partner
  canCancel: Boolean!
  canModify: Boolean!
  createdAt: DateTime!
}

union Fulfillment = DeliveryFulfillment | PickupFulfillment | RidePickupFulfillment

type DeliveryFulfillment {
  driver: Driver
  trackingUrl: String
  estimatedArrival: DateTime
  currentLocation: GeoLocation
}

type RidePickupFulfillment {
  rideId: ID!
  rideStatus: RideStatus!
  driver: Driver
  orderPickupCode: String!
  merchantLocation: Location!
}
```

### Example Queries

**Get Cart with Items**

```graphql
query GetCart {
  currentCart {
    id
    status
    merchantGroups {
      merchantName
      items {
        name
        quantity
        totalPrice {
          display
        }
      }
      subtotal {
        display
      }
    }
    pricing {
      total {
        display
      }
    }
  }
}
```

**Get Order with Tracking**

```graphql
query GetOrderWithTracking($orderId: ID!) {
  order(id: $orderId) {
    orderNumber
    status
    fulfillment {
      ... on DeliveryFulfillment {
        driver {
          name
          photo
          currentLocation {
            latitude
            longitude
          }
        }
        estimatedArrival
        trackingUrl
      }
      ... on RidePickupFulfillment {
        rideStatus
        orderPickupCode
        driver {
          name
          vehicle {
            licensePlate
          }
        }
      }
    }
  }
}
```

**Subscribe to Order Updates**

```graphql
subscription OnOrderUpdate($orderId: ID!) {
  orderUpdated(orderId: $orderId) {
    type
    status
    location {
      latitude
      longitude
    }
    etaMinutes
    timestamp
  }
}
```

---

## Rate Limits

| Endpoint Category | Rate Limit | Window |
|-------------------|------------|--------|
| Cart Read | 100 | 1 minute |
| Cart Write | 30 | 1 minute |
| Order Read | 60 | 1 minute |
| Order Write | 10 | 1 minute |
| Checkout | 5 | 1 minute |
| WebSocket Connections | 5 | concurrent |

---

## Method Prototypes (TypeScript SDK)

```typescript
// Uber Cart SDK
interface UberCartClient {
  // Authentication
  setAccessToken(token: string): void;

  // Cart operations
  cart: {
    getCurrent(): Promise<Cart>;
    getById(cartId: string): Promise<Cart>;
    create(input: CreateCartInput): Promise<Cart>;
    addItem(cartId: string, item: CartItemInput): Promise<AddItemResult>;
    updateItem(cartId: string, itemId: string, update: CartItemUpdate): Promise<CartItem>;
    removeItem(cartId: string, itemId: string): Promise<RemoveItemResult>;
    applyPromoCode(cartId: string, code: string): Promise<PromoCodeResult>;
    validate(cartId: string): Promise<ValidationResult>;
    checkout(cartId: string, input: CheckoutInput): Promise<CheckoutResult>;
  };

  // Order operations
  orders: {
    list(filters?: OrderFilters): Promise<PaginatedOrders>;
    getById(orderId: string): Promise<Order>;
    cancel(orderId: string, reason: CancelReason): Promise<Order>;
    modify(orderId: string, modification: OrderModification): Promise<Order>;
    track(orderId: string, onUpdate: (update: OrderUpdate) => void): WebSocketConnection;
  };

  // Family/Sub-user operations
  family: {
    getSubUsers(): Promise<SubUser[]>;
    createSubUser(input: CreateSubUserInput): Promise<SubUser>;
    updateRestrictions(subUserId: string, restrictions: SubUserRestrictions): Promise<SubUser>;
    getSubUserOrders(subUserId: string): Promise<Order[]>;
  };
}

// Type definitions
interface CartItemInput {
  itemId: string;
  merchantId: string;
  quantity: number;
  customizations?: Record<string, CustomizationSelection>;
  specialNotes?: string;
}

interface CheckoutInput {
  paymentMethodId: string;
  tipAmount?: Money;
  deliveryInstructions?: string;
  contactPhone?: string;
}

interface OrderModification {
  itemsToAdd?: CartItemInput[];
  itemsToRemove?: string[];
  itemsToUpdate?: { itemId: string; quantity?: number; specialNotes?: string }[];
  deliveryAddress?: Address;
  specialNotes?: string;
}

interface OrderFilters {
  status?: OrderStatus[];
  fulfillmentType?: FulfillmentType;
  fromDate?: Date;
  toDate?: Date;
  merchantId?: string;
  limit?: number;
  cursor?: string;
}
```

---

## Versioning & Deprecation

### Version Header

```http
X-API-Version: 2024-01-15
```

### Deprecation Notice

Deprecated endpoints include:
```http
Deprecation: true
Sunset: Sat, 15 Jun 2024 00:00:00 GMT
Link: <https://api.uber.com/cart/v2/carts>; rel="successor-version"
```

