# API Specification — Instant Grocery Delivery

**Format:** OpenAPI 3.0.3  
**Base URL:** `https://api.grocery.internal/v1`  
**Auth:** Bearer JWT on all endpoints except `/auth/*`  
**Scale:** 40 dark stores · 100k orders/day · 500 orders/min peak

---

## Endpoint Index

### Orders
| Method | Path | Summary |
|--------|------|---------|
| `POST` | `/orders` | Place a new order |
| `GET` | `/orders` | List customer order history (cursor-paginated) |
| `GET` | `/orders/{order_id}` | Get order status and details |
| `POST` | `/orders/{order_id}/cancel` | Cancel an order |
| `GET` | `/orders/{order_id}/tracking` | Live rider location and ETA |

### Users & Auth
| Method | Path | Summary |
|--------|------|---------|
| `POST` | `/auth/login` | Send OTP to phone number |
| `POST` | `/auth/verify-otp` | Verify OTP → access + refresh tokens |
| `POST` | `/auth/refresh` | Rotate access token |
| `GET` | `/users/me` | Current user profile |
| `GET` | `/users/me/addresses` | List saved addresses |
| `POST` | `/users/me/addresses` | Add a delivery address |
| `DELETE` | `/users/me/addresses/{address_id}` | Delete an address |

### Catalog
| Method | Path | Summary |
|--------|------|---------|
| `GET` | `/catalog/search` | Full-text fuzzy product search (Elasticsearch, p99 < 200ms) |
| `GET` | `/catalog/autocomplete` | Type-ahead suggestions (Redis sorted set, < 10ms) |
| `GET` | `/catalog/products/{sku_id}` | Full product detail with store stock |
| `GET` | `/catalog/categories` | Category tree for a store |
| `GET` | `/catalog/categories/{category_id}/products` | Browse products in a category |
| `GET` | `/catalog/recommendations` | Personalised homepage feed (pre-computed, 24h TTL) |
| `GET` | `/catalog/substitutes/{sku_id}` | Ranked OOS substitutes for pickers |

### Inventory _(internal / store ops)_
| Method | Path | Summary |
|--------|------|---------|
| `GET` | `/inventory/{store_id}/stock` | Bulk stock check for cart validation |
| `PUT` | `/inventory/{store_id}/restock` | Add incoming stock at dark store |
| `POST` | `/inventory/{store_id}/adjust` | Write-off for spoilage / damage / theft |
| `GET` | `/inventory/{store_id}/low-stock` | Items below reorder threshold |

### Dispatch _(internal / rider app)_
| Method | Path | Summary |
|--------|------|---------|
| `GET` | `/dispatch/riders/nearby` | Find available riders near a location |
| `POST` | `/dispatch/riders/{rider_id}/location` | GPS ping from rider app (every 5s) |
| `GET` | `/dispatch/riders/{rider_id}/status` | Rider status and current assignment |
| `POST` | `/dispatch/riders/{rider_id}/status` | Go online / offline |
| `POST` | `/dispatch/riders/{rider_id}/accept` | Accept an order offer (first-accept wins) |

### ETA
| Method | Path | Summary |
|--------|------|---------|
| `GET` | `/eta/pre-checkout` | Approximate ETA before order (< 100ms) |
| `GET` | `/eta/orders/{order_id}` | Precise ETA for a placed order |
| `GET` | `/eta/stores` | ETA + congestion for all stores near a location |

---

## Key Design Constraints

| Constraint | Value |
|---|---|
| Order placement latency | p99 < 500ms |
| Search latency | p99 < 200ms |
| Autocomplete latency | p99 < 10ms |
| Pre-checkout ETA latency | p99 < 100ms |
| Rider location update interval | Every 5s |
| `Idempotency-Key` required on | `POST /orders` |
| Max items per order | 100 |
| Max SKUs per stock check | 100 |
| Auth scheme | Bearer JWT, OTP-based login |

---

## Full OpenAPI Specification

```yaml
openapi: 3.0.3
info:
  title: Instant Grocery Delivery API
  description: 'API specification for a Blinkit-scale instant grocery delivery platform.

    Covers customer-facing ordering, catalog browsing, inventory management,

    dispatch coordination, and ETA tracking.


    **Scale:** 40 dark stores · 100k orders/day · 500 orders/min peak

    **Delivery SLA:** 10–15 minutes from order placement

    '
  version: 1.0.0
  contact:
    name: Platform Engineering
servers:
- url: https://api.grocery.internal/v1
  description: Production
- url: https://api-staging.grocery.internal/v1
  description: Staging
security:
- BearerAuth: []
tags:
- name: Orders
  description: Order placement, tracking, and lifecycle management
- name: Users
  description: User profiles, addresses, and authentication
- name: Catalog
  description: Product search, browsing, and catalog management
- name: Inventory
  description: Per-store stock levels and reservations
- name: Dispatch
  description: Rider assignment and delivery coordination
- name: ETA
  description: Delivery time estimation and live tracking
paths:
  /orders:
    post:
      tags:
      - Orders
      summary: Place a new order
      description: 'Creates a new order for the authenticated customer. The order transitions

        through the following lifecycle:

        CART_LOCKED → PAYMENT_PENDING → PAYMENT_CONFIRMED → INVENTORY_RESERVED

        → PICKING → PACKED → RIDER_ASSIGNED → OUT_FOR_DELIVERY → DELIVERED


        Provide an `Idempotency-Key` header to safely retry on network failures

        without risk of double-charging.

        '
      operationId: placeOrder
      parameters:
      - name: Idempotency-Key
        in: header
        required: true
        description: 'A unique client-generated key (UUID v4 recommended) to ensure

          idempotent order placement. The server will return the original

          response if the same key is replayed within 24 hours.

          '
        schema:
          type: string
          format: uuid
          example: a1b2c3d4-e5f6-7890-abcd-ef1234567890
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/OrderRequest'
            example:
              store_id: store-mum-andheri-01
              items:
              - sku_id: SKU-AMUL-MILK-500ML
                qty: 2
              - sku_id: SKU-BREAD-BRITANNIA-400G
                qty: 1
              payment_method_id: pm-upi-9876543210
              delivery_address_id: addr-7f3a2b1c
      responses:
        '201':
          description: Order placed successfully
          headers:
            Location:
              description: URL of the newly created order resource
              schema:
                type: string
                example: /v1/orders/ord-550e8400-e29b-41d4
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/OrderResponse'
              example:
                order_id: ord-550e8400-e29b-41d4
                status: PAYMENT_PENDING
                store_id: store-mum-andheri-01
                items:
                - sku_id: SKU-AMUL-MILK-500ML
                  name: Amul Taaza Toned Milk 500ml
                  qty: 2
                  unit_price: 28.0
                  total_price: 56.0
                  image_url: https://cdn.grocery.internal/images/SKU-AMUL-MILK-500ML.jpg
                - sku_id: SKU-BREAD-BRITANNIA-400G
                  name: Britannia 100% Whole Wheat Bread 400g
                  qty: 1
                  unit_price: 45.0
                  total_price: 45.0
                  image_url: https://cdn.grocery.internal/images/SKU-BREAD-BRITANNIA-400G.jpg
                total_amount: 101.0
                currency: INR
                eta_minutes: 12
                rider: null
                created_at: '2026-02-22T09:15:00Z'
                updated_at: '2026-02-22T09:15:00Z'
        '402':
          description: Payment failed
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: PAYMENT_FAILED
                message: Payment could not be processed. Please verify your payment method and try again.
                details:
                  payment_method_id: pm-upi-9876543210
                  gateway_error_code: INSUFFICIENT_FUNDS
        '409':
          description: One or more items are out of stock
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: INSUFFICIENT_STOCK
                message: Some items in your cart are no longer available.
                details:
                  out_of_stock_skus:
                  - SKU-AMUL-MILK-500ML
        '422':
          description: Validation error — malformed request body
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: VALIDATION_ERROR
                message: Request body failed validation.
                details:
                  fields:
                  - field: items[0].qty
                    issue: must be between 1 and 50
    get:
      tags:
      - Orders
      summary: List customer's order history
      description: 'Returns a paginated list of orders placed by the authenticated customer,

        ordered by creation time descending (most recent first).

        Use `cursor` from the previous response''s `next_cursor` to fetch the

        next page.

        '
      operationId: listOrders
      parameters:
      - name: limit
        in: query
        required: false
        description: Maximum number of orders to return per page. Default is 20, maximum is 100.
        schema:
          type: integer
          minimum: 1
          maximum: 100
          default: 20
          example: 20
      - name: cursor
        in: query
        required: false
        description: 'Opaque pagination cursor returned in the previous response''s

          `next_cursor` field. Omit on the first request.

          '
        schema:
          type: string
          example: eyJvcmRlcl9pZCI6Im9yZC01NTBlODQwMCIsInRzIjoiMjAyNi0wMi0yMlQwOToxNTowMFoifQ==
      responses:
        '200':
          description: Paginated list of orders
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/OrderListResponse'
              example:
                items:
                - order_id: ord-550e8400-e29b-41d4
                  status: DELIVERED
                  store_id: store-mum-andheri-01
                  items:
                  - sku_id: SKU-AMUL-MILK-500ML
                    name: Amul Taaza Toned Milk 500ml
                    qty: 2
                    unit_price: 28.0
                    total_price: 56.0
                    image_url: https://cdn.grocery.internal/images/SKU-AMUL-MILK-500ML.jpg
                  total_amount: 56.0
                  currency: INR
                  eta_minutes: null
                  rider: null
                  created_at: '2026-02-21T18:30:00Z'
                  updated_at: '2026-02-21T18:44:22Z'
                next_cursor: eyJvcmRlcl9pZCI6Im9yZC01NTBlODQwMCIsInRzIjoiMjAyNi0wMi0yMVQxODozMDowMFoifQ==
                total: 47
  /orders/{order_id}:
    get:
      tags:
      - Orders
      summary: Get order status and details
      description: 'Returns the full details of a single order including its current status,

        itemised breakdown, and rider information if the order has been assigned

        to a rider.

        '
      operationId: getOrder
      parameters:
      - name: order_id
        in: path
        required: true
        description: Unique identifier of the order (UUID format)
        schema:
          type: string
          format: uuid
          example: ord-550e8400-e29b-41d4
      responses:
        '200':
          description: Order found and returned
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/OrderResponse'
              example:
                order_id: ord-550e8400-e29b-41d4
                status: RIDER_ASSIGNED
                store_id: store-mum-andheri-01
                items:
                - sku_id: SKU-AMUL-MILK-500ML
                  name: Amul Taaza Toned Milk 500ml
                  qty: 2
                  unit_price: 28.0
                  total_price: 56.0
                  image_url: https://cdn.grocery.internal/images/SKU-AMUL-MILK-500ML.jpg
                total_amount: 56.0
                currency: INR
                eta_minutes: 8
                rider:
                  rider_id: rider-8821
                  name: Ravi Kumar
                  phone_masked: '******7654'
                  vehicle_type: BIKE
                created_at: '2026-02-22T09:15:00Z'
                updated_at: '2026-02-22T09:21:10Z'
        '404':
          description: Order not found
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: ORDER_NOT_FOUND
                message: No order found with the provided ID.
                details:
                  order_id: ord-550e8400-e29b-41d4
  /orders/{order_id}/cancel:
    post:
      tags:
      - Orders
      summary: Cancel an order
      description: 'Cancels an in-flight order. Cancellation is only permitted when the order

        is in one of the following states:

        - `CART_LOCKED`

        - `PAYMENT_PENDING`

        - `INVENTORY_RESERVED`

        - `PICKING`


        Once an order has been `PACKED` or beyond, cancellation is no longer

        allowed and a 409 is returned.

        '
      operationId: cancelOrder
      parameters:
      - name: order_id
        in: path
        required: true
        description: Unique identifier of the order to cancel
        schema:
          type: string
          format: uuid
          example: ord-550e8400-e29b-41d4
      responses:
        '200':
          description: Order successfully cancelled
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/OrderResponse'
              example:
                order_id: ord-550e8400-e29b-41d4
                status: CANCELLED
                store_id: store-mum-andheri-01
                items:
                - sku_id: SKU-AMUL-MILK-500ML
                  name: Amul Taaza Toned Milk 500ml
                  qty: 2
                  unit_price: 28.0
                  total_price: 56.0
                  image_url: null
                total_amount: 56.0
                currency: INR
                eta_minutes: null
                rider: null
                created_at: '2026-02-22T09:15:00Z'
                updated_at: '2026-02-22T09:17:45Z'
        '404':
          description: Order not found
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: ORDER_NOT_FOUND
                message: No order found with the provided ID.
                details: null
        '409':
          description: Order has already been packed or dispatched — cancellation not allowed
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: CANCELLATION_NOT_ALLOWED
                message: Order cannot be cancelled once it has been packed or dispatched.
                details:
                  current_status: PACKED
                  cancellable_statuses:
                  - CART_LOCKED
                  - PAYMENT_PENDING
                  - INVENTORY_RESERVED
                  - PICKING
  /orders/{order_id}/tracking:
    get:
      tags:
      - Orders
      summary: Get live tracking info for an order
      description: 'Returns real-time location and ETA data for an order that is currently

        `OUT_FOR_DELIVERY`. The rider''s coordinates are updated every 10 seconds

        by the dispatch service.


        Returns 409 if the order exists but is not yet in `OUT_FOR_DELIVERY`

        state (e.g., still being picked or packed).

        '
      operationId: getOrderTracking
      parameters:
      - name: order_id
        in: path
        required: true
        description: Unique identifier of the order to track
        schema:
          type: string
          format: uuid
          example: ord-550e8400-e29b-41d4
      responses:
        '200':
          description: Live tracking data returned
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/TrackingResponse'
              example:
                rider_name: Ravi Kumar
                phone_masked: '******7654'
                lat: 19.11832
                lng: 72.84621
                eta_minutes_remaining: 4
                status: OUT_FOR_DELIVERY
        '404':
          description: Order not found
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: ORDER_NOT_FOUND
                message: No order found with the provided ID.
                details: null
        '409':
          description: Order is not yet out for delivery
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: TRACKING_UNAVAILABLE
                message: Live tracking is only available once the order is out for delivery.
                details:
                  current_status: PICKING
  /auth/login:
    post:
      tags:
      - Users
      summary: Send OTP to phone number (login step 1)
      description: 'Initiates the OTP-based authentication flow by sending a one-time

        password to the provided phone number via SMS. The OTP is valid for

        `expires_in_seconds` seconds.


        This endpoint does **not** require an access token.

        '
      operationId: sendLoginOtp
      security: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/LoginRequest'
            example:
              phone_number: '+919876543210'
      responses:
        '200':
          description: OTP sent successfully
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/OTPSentResponse'
              example:
                message: OTP sent to +919876543210
                expires_in_seconds: 300
        '422':
          description: Invalid phone number format
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: VALIDATION_ERROR
                message: phone_number must be in E.164 format (e.g., +919876543210).
                details:
                  field: phone_number
        '429':
          description: Too many OTP requests — rate limit exceeded
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: RATE_LIMIT_EXCEEDED
                message: Too many OTP requests. Please wait before trying again.
                details:
                  retry_after_seconds: 60
  /auth/verify-otp:
    post:
      tags:
      - Users
      summary: Verify OTP and obtain access token (login step 2)
      description: 'Verifies the OTP submitted by the user against the one sent in step 1.

        On success, returns a short-lived `access_token` (JWT) and a long-lived

        `refresh_token`. A new user record is created if this is the first login

        for the given phone number.


        This endpoint does **not** require an access token.

        '
      operationId: verifyOtp
      security: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/OTPVerifyRequest'
            example:
              phone_number: '+919876543210'
              otp: '482917'
      responses:
        '200':
          description: OTP verified — access token issued
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/AuthResponse'
              example:
                access_token: eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c3ItYTFiMmMzZDQiLCJwaG9uZSI6Iis5MTk4NzY1NDMyMTAiLCJpYXQiOjE3NDA2NDE0MDAsImV4cCI6MTc0MDY0NTAwMH0.signature
                refresh_token: rt-8f4e2a1b9d7c6e3f0a5b2d8e1c4f7a9b
                expires_in: 3600
                user_id: usr-a1b2c3d4
        '401':
          description: Invalid or expired OTP
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: INVALID_OTP
                message: The OTP provided is incorrect or has expired. Please request a new OTP.
                details:
                  attempts_remaining: 2
  /auth/refresh:
    post:
      tags:
      - Users
      summary: Refresh access token
      description: 'Exchanges a valid `refresh_token` for a new `access_token`. The refresh

        token itself is rotated on every use (refresh token rotation) to limit

        the window of exposure if a token is compromised.

        '
      operationId: refreshToken
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/RefreshRequest'
            example:
              refresh_token: rt-8f4e2a1b9d7c6e3f0a5b2d8e1c4f7a9b
      responses:
        '200':
          description: New access token issued
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/AuthResponse'
              example:
                access_token: eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.new_payload.new_signature
                refresh_token: rt-9c5f3b2a0e8d7f4e1b6c3e9f2d5a8b1c
                expires_in: 3600
                user_id: usr-a1b2c3d4
        '401':
          description: Refresh token is invalid, expired, or already rotated
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: INVALID_REFRESH_TOKEN
                message: The refresh token is invalid or has already been used. Please log in again.
                details: null
  /users/me:
    get:
      tags:
      - Users
      summary: Get current user profile
      description: Returns the profile of the currently authenticated user.
      operationId: getCurrentUser
      responses:
        '200':
          description: User profile returned
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/UserProfile'
              example:
                user_id: usr-a1b2c3d4
                name: Priya Sharma
                phone_number: '+919876543210'
                email: priya.sharma@example.com
                created_at: '2025-08-15T10:22:00Z'
        '401':
          description: Missing or invalid access token
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: UNAUTHORIZED
                message: A valid Bearer token is required.
                details: null
  /users/me/addresses:
    get:
      tags:
      - Users
      summary: List saved delivery addresses
      description: 'Returns all saved delivery addresses for the authenticated user. The

        default address (if set) is indicated by `is_default: true`.

        '
      operationId: listAddresses
      responses:
        '200':
          description: List of saved addresses
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: '#/components/schemas/Address'
              example:
              - address_id: addr-7f3a2b1c
                label: HOME
                line1: Flat 4B, Anand Nagar CHS
                line2: Near Lokhandwala Market
                city: Mumbai
                pincode: '400053'
                lat: 19.13621
                lng: 72.83507
                is_default: true
              - address_id: addr-c9e4d5f0
                label: WORK
                line1: 12th Floor, Inspire BKC
                line2: Bandra Kurla Complex
                city: Mumbai
                pincode: '400051'
                lat: 19.06522
                lng: 72.86841
                is_default: false
    post:
      tags:
      - Users
      summary: Add a new delivery address
      description: 'Saves a new delivery address to the authenticated user''s account.

        If `is_default` is set to `true`, any existing default address will

        be demoted automatically.

        '
      operationId: addAddress
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AddressRequest'
            example:
              label: HOME
              line1: Flat 4B, Anand Nagar CHS
              line2: Near Lokhandwala Market
              city: Mumbai
              pincode: '400053'
              lat: 19.13621
              lng: 72.83507
              is_default: true
      responses:
        '201':
          description: Address created successfully
          headers:
            Location:
              description: URL of the newly created address resource
              schema:
                type: string
                example: /v1/users/me/addresses/addr-7f3a2b1c
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Address'
              example:
                address_id: addr-7f3a2b1c
                label: HOME
                line1: Flat 4B, Anand Nagar CHS
                line2: Near Lokhandwala Market
                city: Mumbai
                pincode: '400053'
                lat: 19.13621
                lng: 72.83507
                is_default: true
        '422':
          description: Validation error
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: VALIDATION_ERROR
                message: Request body failed validation.
                details:
                  fields:
                  - field: pincode
                    issue: must be exactly 6 digits
  /users/me/addresses/{address_id}:
    delete:
      tags:
      - Users
      summary: Delete a saved address
      description: 'Permanently removes a saved delivery address. If the deleted address was

        the default, no new default is automatically promoted — the client

        should prompt the user to select a new default.

        '
      operationId: deleteAddress
      parameters:
      - name: address_id
        in: path
        required: true
        description: Unique identifier of the address to delete
        schema:
          type: string
          example: addr-7f3a2b1c
      responses:
        '204':
          description: Address deleted successfully — no content returned
        '404':
          description: Address not found
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: ADDRESS_NOT_FOUND
                message: No address found with the provided ID.
                details:
                  address_id: addr-7f3a2b1c
  /catalog/search:
    get:
      tags:
      - Catalog
      summary: Search products at a specific dark store
      description: 'Full-text fuzzy search with in-stock filtering. Backed by a per-store Elasticsearch index. Supports category
        filtering and sort ordering. p99 latency target < 200ms.

        '
      operationId: catalogSearch
      parameters:
      - name: q
        in: query
        required: true
        description: Search query string (e.g. "amul butter")
        schema:
          type: string
          example: amul butter
      - name: store_id
        in: query
        required: true
        description: UUID of the dark store to search inventory for
        schema:
          type: string
          format: uuid
          example: 3fa85f64-5717-4562-b3fc-2c963f66afa6
      - name: limit
        in: query
        required: false
        description: Maximum number of results to return
        schema:
          type: integer
          default: 20
          maximum: 50
          minimum: 1
          example: 20
      - name: offset
        in: query
        required: false
        description: Number of results to skip for pagination
        schema:
          type: integer
          default: 0
          minimum: 0
          example: 0
      - name: category_id
        in: query
        required: false
        description: Optional category filter to narrow results
        schema:
          type: string
          example: dairy-and-eggs
      - name: sort
        in: query
        required: false
        description: Sort order for results
        schema:
          type: string
          enum:
          - RELEVANCE
          - PRICE_ASC
          - PRICE_DESC
          default: RELEVANCE
          example: RELEVANCE
      responses:
        '200':
          description: Successful search response
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SearchResponse'
              example:
                query: amul butter
                items:
                - sku_id: SKU-AMUL-BTR-500
                  name: Amul Butter
                  brand: Amul
                  category_id: dairy-and-eggs
                  category_name: Dairy & Eggs
                  price: 56.0
                  original_price: null
                  unit: 500g
                  image_url: https://cdn.groceryapp.example/images/SKU-AMUL-BTR-500.webp
                  in_stock: true
                  stock_count: null
                  tags:
                  - bestseller
                total: 1
                took_ms: 43
                offset: 0
                limit: 20
        '400':
          description: Invalid query parameters
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                error: BAD_REQUEST
                message: Query parameter 'q' is required and must not be blank.
                request_id: req-abc123
  /catalog/autocomplete:
    get:
      tags:
      - Catalog
      summary: Type-ahead suggestions for search bar
      description: 'Returns autocomplete suggestions for partial search input. Served directly from a Redis sorted set — no
        Elasticsearch involved. Response latency target < 10ms.

        '
      operationId: catalogAutocomplete
      parameters:
      - name: q
        in: query
        required: true
        description: Partial search query (minimum 2 characters)
        schema:
          type: string
          minLength: 2
          example: am
      - name: store_id
        in: query
        required: true
        description: UUID of the dark store
        schema:
          type: string
          format: uuid
          example: 3fa85f64-5717-4562-b3fc-2c963f66afa6
      - name: limit
        in: query
        required: false
        description: Maximum number of suggestions to return
        schema:
          type: integer
          default: 8
          maximum: 10
          minimum: 1
          example: 8
      responses:
        '200':
          description: Autocomplete suggestions returned successfully
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/AutocompleteResponse'
              example:
                query: am
                suggestions:
                - amul butter
                - amul milk
                - amul paneer
                - amul cheese
                - amul curd
        '400':
          description: Invalid query parameters
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                error: BAD_REQUEST
                message: Query parameter 'q' must be at least 2 characters.
                request_id: req-def456
  /catalog/products/{sku_id}:
    get:
      tags:
      - Catalog
      summary: Get full product detail
      description: 'Returns comprehensive product information including images, nutritional data, stock availability, and
        pricing for the specified SKU at a given store.

        '
      operationId: getProductDetail
      parameters:
      - name: sku_id
        in: path
        required: true
        description: Unique SKU identifier of the product
        schema:
          type: string
          example: SKU-AMUL-BTR-500
      - name: store_id
        in: query
        required: true
        description: UUID of the dark store — required to resolve stock and pricing for that store
        schema:
          type: string
          format: uuid
          example: 3fa85f64-5717-4562-b3fc-2c963f66afa6
      responses:
        '200':
          description: Product detail returned successfully
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ProductDetail'
              example:
                sku_id: SKU-AMUL-BTR-500
                name: Amul Butter
                brand: Amul
                category_id: dairy-and-eggs
                category_name: Dairy & Eggs
                price: 56.0
                original_price: 60.0
                unit: 500g
                image_url: https://cdn.groceryapp.example/images/SKU-AMUL-BTR-500.webp
                in_stock: true
                stock_count: 8
                tags:
                - bestseller
                description: Amul Butter is pasteurised butter made from fresh cream. It is rich in vitamins A, D, and E.
                images:
                - https://cdn.groceryapp.example/images/SKU-AMUL-BTR-500.webp
                - https://cdn.groceryapp.example/images/SKU-AMUL-BTR-500-back.webp
                weight_grams: 500
                nutritional_info:
                  calories: 717
                  protein: 0.9
                  carbs: 0.1
                  fat: 81.0
                manufacturer: Gujarat Cooperative Milk Marketing Federation Ltd.
                country_of_origin: India
                shelf_life_days: 90
                is_sponsored: false
        '404':
          description: Product not found
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                error: NOT_FOUND
                message: Product with SKU 'SKU-AMUL-BTR-500' was not found.
                request_id: req-ghi789
  /catalog/categories:
    get:
      tags:
      - Catalog
      summary: List all product categories for a store
      description: 'Returns the full category tree for a given dark store, including subcategory nesting and product counts.

        '
      operationId: listCategories
      parameters:
      - name: store_id
        in: query
        required: true
        description: UUID of the dark store
        schema:
          type: string
          format: uuid
          example: 3fa85f64-5717-4562-b3fc-2c963f66afa6
      responses:
        '200':
          description: Category list returned successfully
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: '#/components/schemas/Category'
              example:
              - category_id: dairy-and-eggs
                name: Dairy & Eggs
                slug: dairy-and-eggs
                icon_url: https://cdn.groceryapp.example/icons/dairy.svg
                product_count: 142
                subcategories:
                - category_id: butter-and-ghee
                  name: Butter & Ghee
                  slug: butter-and-ghee
                  icon_url: null
                  product_count: 23
                  subcategories: null
                - category_id: milk
                  name: Milk
                  slug: milk
                  icon_url: null
                  product_count: 31
                  subcategories: null
  /catalog/categories/{category_id}/products:
    get:
      tags:
      - Catalog
      summary: Browse all products in a category
      description: 'Returns paginated product listings for a given category at a specific store. Supports sort ordering including
        popularity ranking.

        '
      operationId: getCategoryProducts
      parameters:
      - name: category_id
        in: path
        required: true
        description: Unique identifier of the category
        schema:
          type: string
          example: dairy-and-eggs
      - name: store_id
        in: query
        required: true
        description: UUID of the dark store
        schema:
          type: string
          format: uuid
          example: 3fa85f64-5717-4562-b3fc-2c963f66afa6
      - name: limit
        in: query
        required: false
        description: Maximum number of products to return
        schema:
          type: integer
          default: 40
          maximum: 100
          minimum: 1
          example: 40
      - name: offset
        in: query
        required: false
        description: Number of products to skip for pagination
        schema:
          type: integer
          default: 0
          minimum: 0
          example: 0
      - name: sort
        in: query
        required: false
        description: Sort order for products
        schema:
          type: string
          enum:
          - RELEVANCE
          - PRICE_ASC
          - PRICE_DESC
          - POPULARITY
          default: RELEVANCE
          example: POPULARITY
      responses:
        '200':
          description: Product list for category returned successfully
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ProductListResponse'
              example:
                items:
                - sku_id: SKU-AMUL-BTR-500
                  name: Amul Butter
                  brand: Amul
                  category_id: dairy-and-eggs
                  category_name: Dairy & Eggs
                  price: 56.0
                  original_price: null
                  unit: 500g
                  image_url: https://cdn.groceryapp.example/images/SKU-AMUL-BTR-500.webp
                  in_stock: true
                  stock_count: null
                  tags:
                  - bestseller
                total: 142
                category:
                  category_id: dairy-and-eggs
                  name: Dairy & Eggs
                  slug: dairy-and-eggs
                  icon_url: https://cdn.groceryapp.example/icons/dairy.svg
                  product_count: 142
                  subcategories: null
                offset: 0
                limit: 40
  /catalog/recommendations:
    get:
      tags:
      - Catalog
      summary: Get personalised product recommendations for homepage feed
      description: 'Returns pre-computed personalised recommendations for a user at a given store. Recommendations are computed
        offline with up to 24 hours of staleness. In-stock filtering is applied at serve time. Cold-start users receive non-personalised
        trending or editorial recommendations.

        '
      operationId: getRecommendations
      parameters:
      - name: store_id
        in: query
        required: true
        description: UUID of the dark store
        schema:
          type: string
          format: uuid
          example: 3fa85f64-5717-4562-b3fc-2c963f66afa6
      - name: limit
        in: query
        required: false
        description: Maximum number of recommendations to return
        schema:
          type: integer
          default: 20
          maximum: 50
          minimum: 1
          example: 20
      - name: section
        in: query
        required: false
        description: Recommendation section / feed type
        schema:
          type: string
          enum:
          - FOR_YOU
          - FREQUENTLY_BOUGHT
          - TRENDING
          - NEW_ARRIVALS
          default: FOR_YOU
          example: FOR_YOU
      responses:
        '200':
          description: Recommendations returned successfully
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/RecommendationResponse'
              example:
                items:
                - sku_id: SKU-NESTLE-MILO-400
                  name: Milo Energy Drink Mix
                  brand: Nestle
                  category_id: beverages
                  category_name: Beverages
                  price: 210.0
                  original_price: 230.0
                  unit: 400g
                  image_url: https://cdn.groceryapp.example/images/SKU-NESTLE-MILO-400.webp
                  in_stock: true
                  stock_count: null
                  tags:
                  - bestseller
                  - offer
                section: FOR_YOU
                is_personalised: true
                store_id: 3fa85f64-5717-4562-b3fc-2c963f66afa6
  /catalog/substitutes/{sku_id}:
    get:
      tags:
      - Catalog
      summary: Get substitute products for an out-of-stock item
      description: 'Returns ranked substitute products for a given SKU that is out of stock at the specified store. Primarily
        used during the picking stage when a picker marks an item as unavailable. Substitutes are drawn from the same category
        and ranked by similarity score.

        '
      operationId: getSubstitutes
      parameters:
      - name: sku_id
        in: path
        required: true
        description: SKU identifier of the out-of-stock product
        schema:
          type: string
          example: SKU-AMUL-BTR-500
      - name: store_id
        in: query
        required: true
        description: UUID of the dark store
        schema:
          type: string
          format: uuid
          example: 3fa85f64-5717-4562-b3fc-2c963f66afa6
      responses:
        '200':
          description: Substitutes returned successfully
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SubstituteResponse'
              example:
                original_sku_id: SKU-AMUL-BTR-500
                substitutes:
                - sku_id: SKU-AMUL-BTR-100
                  name: Amul Butter
                  brand: Amul
                  category_id: dairy-and-eggs
                  category_name: Dairy & Eggs
                  price: 12.0
                  original_price: null
                  unit: 100g
                  image_url: https://cdn.groceryapp.example/images/SKU-AMUL-BTR-100.webp
                  in_stock: true
                  stock_count: 5
                  tags:
                  - bestseller
                  similarity_reason: SAME_BRAND_SAME_CATEGORY
                - sku_id: SKU-MOTHER-DAIRY-BTR-500
                  name: Mother Dairy Butter
                  brand: Mother Dairy
                  category_id: dairy-and-eggs
                  category_name: Dairy & Eggs
                  price: 54.0
                  original_price: null
                  unit: 500g
                  image_url: https://cdn.groceryapp.example/images/SKU-MOTHER-DAIRY-BTR-500.webp
                  in_stock: true
                  stock_count: null
                  tags: []
                  similarity_reason: DIFFERENT_BRAND_SAME_CATEGORY
        '404':
          description: No substitutes found for the given SKU
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                error: NOT_FOUND
                message: No substitutes available for SKU 'SKU-AMUL-BTR-500' at this store.
                request_id: req-jkl012
  /inventory/{store_id}/stock:
    get:
      tags:
      - Inventory
      summary: Check stock levels for a list of SKUs at a store
      description: 'Reads from Redis hot layer. Used pre-checkout to validate cart. p99 < 50ms.

        '
      operationId: checkStock
      parameters:
      - name: store_id
        in: path
        required: true
        schema:
          type: string
          format: uuid
        example: a1b2c3d4-e5f6-7890-abcd-ef1234567890
      - name: sku_ids
        in: query
        required: true
        description: 'Comma-separated list of SKU IDs or repeated query parameters. Maximum 100 items.

          '
        schema:
          type: array
          items:
            type: string
          maxItems: 100
        style: form
        explode: false
        example:
        - SKU-001
        - SKU-002
        - SKU-003
      responses:
        '200':
          description: Stock levels for the requested SKUs
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/StockCheckResponse'
              example:
                store_id: a1b2c3d4-e5f6-7890-abcd-ef1234567890
                checked_at: '2026-02-22T10:15:00Z'
                items:
                - sku_id: SKU-001
                  qty_available: 24
                  in_stock: true
                - sku_id: SKU-002
                  qty_available: 0
                  in_stock: false
                - sku_id: SKU-003
                  qty_available: 5
                  in_stock: true
        '404':
          description: Store not found
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: STORE_NOT_FOUND
                message: No store found with ID a1b2c3d4-e5f6-7890-abcd-ef1234567890
  /inventory/{store_id}/restock:
    put:
      tags:
      - Inventory
      summary: Restock items at a dark store (internal, store ops only)
      description: 'Called by store staff when new stock arrives. Updates Redis immediately, async PG write-behind.

        '
      operationId: restockItems
      security:
      - BearerAuth: []
      parameters:
      - name: store_id
        in: path
        required: true
        schema:
          type: string
          format: uuid
        example: a1b2c3d4-e5f6-7890-abcd-ef1234567890
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/RestockRequest'
            example:
              items:
              - sku_id: SKU-001
                qty_added: 50
                batch_id: BATCH-2026-022-001
                expiry_date: '2026-06-30'
              - sku_id: SKU-002
                qty_added: 100
                batch_id: null
                expiry_date: null
      responses:
        '200':
          description: Restock successful
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/RestockResponse'
              example:
                store_id: a1b2c3d4-e5f6-7890-abcd-ef1234567890
                items:
                - sku_id: SKU-001
                  new_qty_available: 74
                  updated_at: '2026-02-22T10:20:00Z'
                - sku_id: SKU-002
                  new_qty_available: 100
                  updated_at: '2026-02-22T10:20:00Z'
        '403':
          description: Forbidden — caller does not have STORE_OPS role
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: FORBIDDEN
                message: Role STORE_OPS required to perform this action
        '404':
          description: Store not found
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: STORE_NOT_FOUND
                message: No store found with ID a1b2c3d4-e5f6-7890-abcd-ef1234567890
  /inventory/{store_id}/adjust:
    post:
      tags:
      - Inventory
      summary: Adjust inventory for spoilage, damage, or write-off (internal)
      operationId: adjustInventory
      security:
      - BearerAuth: []
      parameters:
      - name: store_id
        in: path
        required: true
        schema:
          type: string
          format: uuid
        example: a1b2c3d4-e5f6-7890-abcd-ef1234567890
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AdjustmentRequest'
            example:
              items:
              - sku_id: SKU-005
                qty_change: -3
                reason: SPOILAGE
              - sku_id: SKU-009
                qty_change: -1
                reason: DAMAGE
      responses:
        '200':
          description: Adjustment applied successfully
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/AdjustmentResponse'
              example:
                store_id: a1b2c3d4-e5f6-7890-abcd-ef1234567890
                items:
                - sku_id: SKU-005
                  previous_qty: 12
                  new_qty: 9
                  reason: SPOILAGE
                  adjusted_at: '2026-02-22T11:00:00Z'
                - sku_id: SKU-009
                  previous_qty: 4
                  new_qty: 3
                  reason: DAMAGE
                  adjusted_at: '2026-02-22T11:00:00Z'
        '403':
          description: Forbidden — caller does not have STORE_OPS role
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: FORBIDDEN
                message: Role STORE_OPS required to perform this action
        '409':
          description: Adjustment would result in negative stock
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: NEGATIVE_STOCK_CONFLICT
                message: Adjustment would result in negative stock for SKU-005
                details:
                  sku_id: SKU-005
                  current_qty: 2
                  requested_qty_change: -3
  /inventory/{store_id}/low-stock:
    get:
      tags:
      - Inventory
      summary: Get items below reorder threshold at a store (internal, ops dashboard)
      operationId: getLowStockItems
      parameters:
      - name: store_id
        in: path
        required: true
        schema:
          type: string
          format: uuid
        example: a1b2c3d4-e5f6-7890-abcd-ef1234567890
      - name: threshold
        in: query
        required: false
        schema:
          type: integer
          default: 5
          minimum: 1
        example: 5
      - name: limit
        in: query
        required: false
        schema:
          type: integer
          default: 50
          maximum: 200
          minimum: 1
        example: 50
      responses:
        '200':
          description: List of items below reorder threshold
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/LowStockResponse'
              example:
                store_id: a1b2c3d4-e5f6-7890-abcd-ef1234567890
                items:
                - sku_id: SKU-012
                  name: Organic Whole Milk 1L
                  current_qty: 2
                  threshold: 5
                  last_restocked_at: '2026-02-21T08:30:00Z'
                - sku_id: SKU-034
                  name: Free Range Eggs (6 pack)
                  current_qty: 0
                  threshold: 10
                  last_restocked_at: null
        '404':
          description: Store not found
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: STORE_NOT_FOUND
                message: No store found with ID a1b2c3d4-e5f6-7890-abcd-ef1234567890
  /dispatch/riders/nearby:
    get:
      tags:
      - Dispatch
      summary: Get available riders near a location (internal, dispatch engine)
      description: 'PostGIS GEORADIUS query. Used by Dispatch Service internally, exposed for ops dashboards.

        '
      operationId: getNearbyRiders
      parameters:
      - name: lat
        in: query
        required: true
        schema:
          type: number
          format: double
          minimum: -90
          maximum: 90
        example: 12.9716
      - name: lng
        in: query
        required: true
        schema:
          type: number
          format: double
          minimum: -180
          maximum: 180
        example: 77.5946
      - name: radius_km
        in: query
        required: false
        schema:
          type: number
          format: double
          default: 3.0
          maximum: 10.0
          minimum: 0.1
        example: 3.0
      - name: status
        in: query
        required: false
        schema:
          type: string
          enum:
          - AVAILABLE
          - ON_DELIVERY
          - OFFLINE
          default: AVAILABLE
        example: AVAILABLE
      - name: limit
        in: query
        required: false
        schema:
          type: integer
          default: 10
          maximum: 50
          minimum: 1
        example: 10
      responses:
        '200':
          description: List of nearby riders
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/NearbyRidersResponse'
              example:
                riders:
                - rider_id: r1b2c3d4-e5f6-7890-abcd-ef1234567891
                  name: Arjun Sharma
                  lat: 12.972
                  lng: 77.595
                  distance_km: 0.3
                  status: AVAILABLE
                  active_deliveries: 0
                - rider_id: r2c3d4e5-f6a7-8901-bcde-fa2345678902
                  name: Priya Nair
                  lat: 12.973
                  lng: 77.596
                  distance_km: 0.8
                  status: AVAILABLE
                  active_deliveries: 0
                total: 2
                radius_km: 3.0
  /dispatch/riders/{rider_id}/location:
    post:
      tags:
      - Dispatch
      summary: Update rider GPS location (called by rider app every 5s)
      description: 'Writes to Redis GEO atomically. Publishes rider.location.updated to Kafka.

        '
      operationId: updateRiderLocation
      parameters:
      - name: rider_id
        in: path
        required: true
        schema:
          type: string
          format: uuid
        example: r1b2c3d4-e5f6-7890-abcd-ef1234567891
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/LocationUpdateRequest'
            example:
              lat: 12.9725
              lng: 77.5952
              accuracy_meters: 8.5
              timestamp: '2026-02-22T10:30:00Z'
      responses:
        '204':
          description: Location updated successfully, no content returned
        '404':
          description: Rider not found
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: RIDER_NOT_FOUND
                message: No rider found with ID r1b2c3d4-e5f6-7890-abcd-ef1234567891
  /dispatch/riders/{rider_id}/status:
    get:
      tags:
      - Dispatch
      summary: Get rider status and current assignment
      operationId: getRiderStatus
      parameters:
      - name: rider_id
        in: path
        required: true
        schema:
          type: string
          format: uuid
        example: r1b2c3d4-e5f6-7890-abcd-ef1234567891
      responses:
        '200':
          description: Current rider status and assignment
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/RiderStatusResponse'
              example:
                rider_id: r1b2c3d4-e5f6-7890-abcd-ef1234567891
                name: Arjun Sharma
                status: ON_DELIVERY
                current_order_id: ord-9a8b7c6d-e5f4-3210-fedc-ba9876543210
                last_location:
                  lat: 12.9722
                  lng: 77.5948
                  updated_at: '2026-02-22T10:29:55Z'
                vehicle_type: BIKE
        '404':
          description: Rider not found
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: RIDER_NOT_FOUND
                message: No rider found with ID r1b2c3d4-e5f6-7890-abcd-ef1234567891
    post:
      tags:
      - Dispatch
      summary: Rider updates their availability status (go online/offline)
      operationId: updateRiderAvailabilityStatus
      parameters:
      - name: rider_id
        in: path
        required: true
        schema:
          type: string
          format: uuid
        example: r1b2c3d4-e5f6-7890-abcd-ef1234567891
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/RiderStatusUpdateRequest'
            example:
              status: AVAILABLE
      responses:
        '200':
          description: Status updated, returns new rider status
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/RiderStatusResponse'
              example:
                rider_id: r1b2c3d4-e5f6-7890-abcd-ef1234567891
                name: Arjun Sharma
                status: AVAILABLE
                current_order_id: null
                last_location:
                  lat: 12.972
                  lng: 77.595
                  updated_at: '2026-02-22T10:31:00Z'
                vehicle_type: BIKE
        '404':
          description: Rider not found
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: RIDER_NOT_FOUND
                message: No rider found with ID r1b2c3d4-e5f6-7890-abcd-ef1234567891
  /dispatch/riders/{rider_id}/accept:
    post:
      tags:
      - Dispatch
      summary: Rider accepts an order offer
      description: 'Optimistic lock — only the first accept wins. Subsequent accepts for the same order receive 409.

        '
      operationId: acceptOrderOffer
      parameters:
      - name: rider_id
        in: path
        required: true
        schema:
          type: string
          format: uuid
        example: r1b2c3d4-e5f6-7890-abcd-ef1234567891
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AcceptOrderRequest'
            example:
              order_id: ord-9a8b7c6d-e5f4-3210-fedc-ba9876543210
      responses:
        '200':
          description: Order accepted successfully
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/AcceptOrderResponse'
              example:
                order_id: ord-9a8b7c6d-e5f4-3210-fedc-ba9876543210
                store_address: 42 MG Road, Indiranagar, Bengaluru 560038
                customer_address: 15/A, 3rd Cross, HSR Layout Sector 2, Bengaluru 560102
                items_count: 7
                estimated_pick_time_minutes: 4
        '409':
          description: Order already assigned to another rider
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: ORDER_ALREADY_ASSIGNED
                message: Order ord-9a8b7c6d-e5f4-3210-fedc-ba9876543210 has already been accepted by another rider
        '410':
          description: Order offer expired (more than 30 seconds since notification)
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: ORDER_OFFER_EXPIRED
                message: The offer for order ord-9a8b7c6d-e5f4-3210-fedc-ba9876543210 expired 12 seconds ago
  /eta/pre-checkout:
    get:
      tags:
      - ETA
      summary: Get estimated delivery time before placing order (approximate)
      description: 'Based on store load (active_orders/picker_count from Redis) and zone travel time cache. Response time
        < 100ms. Used on the cart page to show estimated delivery window before the customer commits to checkout.

        '
      operationId: getPreCheckoutETA
      parameters:
      - name: store_id
        in: query
        required: true
        schema:
          type: string
          format: uuid
        example: a1b2c3d4-e5f6-7890-abcd-ef1234567890
      - name: delivery_lat
        in: query
        required: true
        schema:
          type: number
          format: double
          minimum: -90
          maximum: 90
        example: 12.915
      - name: delivery_lng
        in: query
        required: true
        schema:
          type: number
          format: double
          minimum: -180
          maximum: 180
        example: 77.6229
      - name: item_count
        in: query
        required: true
        description: Number of items in cart, used to estimate T_pick
        schema:
          type: integer
          minimum: 1
        example: 7
      responses:
        '200':
          description: Pre-checkout ETA estimate
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/PreCheckoutETAResponse'
              example:
                eta_minutes: 18
                eta_min: 15
                eta_max: 22
                store_congestion: MEDIUM
                disclaimer: Slightly delayed due to high demand
        '404':
          description: Store not found
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: STORE_NOT_FOUND
                message: No store found with ID a1b2c3d4-e5f6-7890-abcd-ef1234567890
  /eta/orders/{order_id}:
    get:
      tags:
      - ETA
      summary: Get current ETA for a placed order
      description: 'More precise than pre-checkout ETA. Uses actual rider location post-assignment to compute a live travel
        time estimate.

        '
      operationId: getOrderETA
      parameters:
      - name: order_id
        in: path
        required: true
        schema:
          type: string
          format: uuid
        example: ord-9a8b7c6d-e5f4-3210-fedc-ba9876543210
      responses:
        '200':
          description: Live ETA for the placed order
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/OrderETAResponse'
              example:
                order_id: ord-9a8b7c6d-e5f4-3210-fedc-ba9876543210
                eta_minutes_remaining: 11
                phase: OUT_FOR_DELIVERY
                last_updated_at: '2026-02-22T10:45:00Z'
                breakdown:
                  t_pick_minutes: 5
                  t_wait_minutes: 2
                  t_travel_minutes: 9
        '404':
          description: Order not found
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: ORDER_NOT_FOUND
                message: No order found with ID ord-9a8b7c6d-e5f4-3210-fedc-ba9876543210
  /eta/stores:
    get:
      tags:
      - ETA
      summary: Get ETA and load summary for all dark stores serving a location
      description: 'Used to pick the nearest available dark store for a customer. Returns congestion levels and availability
        alongside distance-based ETA estimates.

        '
      operationId: getStoreETAList
      parameters:
      - name: lat
        in: query
        required: true
        schema:
          type: number
          format: double
          minimum: -90
          maximum: 90
        example: 12.915
      - name: lng
        in: query
        required: true
        schema:
          type: number
          format: double
          minimum: -180
          maximum: 180
        example: 77.6229
      - name: radius_km
        in: query
        required: false
        schema:
          type: number
          format: double
          default: 5.0
          minimum: 0.5
          maximum: 20.0
        example: 5.0
      responses:
        '200':
          description: Dark stores within radius with ETA and load summary
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/StoreETAListResponse'
              example:
                stores:
                - store_id: a1b2c3d4-e5f6-7890-abcd-ef1234567890
                  name: Indiranagar Dark Store
                  address: 42 MG Road, Indiranagar, Bengaluru 560038
                  distance_km: 1.4
                  eta_minutes: 14
                  congestion_level: LOW
                  is_available: true
                - store_id: b2c3d4e5-f6a7-8901-bcde-fa2345678901
                  name: Koramangala Dark Store
                  address: 80 Feet Rd, Koramangala 4th Block, Bengaluru 560034
                  distance_km: 3.1
                  eta_minutes: 22
                  congestion_level: HIGH
                  is_available: true
                location:
                  lat: 12.915
                  lng: 77.6229
components:
  securitySchemes:
    BearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
      description: 'JWT issued by the Auth Service. The token payload must contain a `roles` claim. Endpoints marked STORE_OPS
        require the `STORE_OPS` role to be present in that claim.

        '
  schemas:
    OrderRequest:
      type: object
      description: Request payload for placing a new order.
      required:
      - store_id
      - items
      - payment_method_id
      - delivery_address_id
      properties:
        store_id:
          type: string
          description: 'Identifier of the dark store that will fulfill this order. The client

            should select the store returned by the nearest-store lookup endpoint

            based on the delivery address.

            '
          example: store-mum-andheri-01
        items:
          type: array
          description: List of items to order. Must contain at least one item.
          minItems: 1
          maxItems: 100
          items:
            $ref: '#/components/schemas/OrderItemRequest'
        payment_method_id:
          type: string
          description: 'Identifier of a saved payment method belonging to the authenticated

            user (UPI VPA, saved card token, or wallet ID).

            '
          example: pm-upi-9876543210
        delivery_address_id:
          type: string
          description: 'Identifier of a saved delivery address belonging to the authenticated

            user. The address must be within the serviceable radius of `store_id`.

            '
          example: addr-7f3a2b1c
    OrderItemRequest:
      type: object
      description: A single line-item in an order request.
      required:
      - sku_id
      - qty
      properties:
        sku_id:
          type: string
          description: Stock Keeping Unit identifier for the product variant.
          example: SKU-AMUL-MILK-500ML
        qty:
          type: integer
          description: Quantity of this SKU to order.
          minimum: 1
          maximum: 50
          example: 2
    OrderResponse:
      type: object
      description: Full representation of an order, returned after placement or on retrieval.
      required:
      - order_id
      - status
      - store_id
      - items
      - total_amount
      - currency
      - created_at
      - updated_at
      properties:
        order_id:
          type: string
          format: uuid
          description: Globally unique identifier for the order.
          example: ord-550e8400-e29b-41d4
        status:
          type: string
          description: 'Current lifecycle state of the order:

            - `CART_LOCKED`: Items reserved, awaiting payment authorisation

            - `PAYMENT_PENDING`: Payment authorisation in progress

            - `PAYMENT_CONFIRMED`: Payment captured successfully

            - `INVENTORY_RESERVED`: Stock confirmed and reserved at the store

            - `PICKING`: Store picker is collecting items

            - `PACKED`: Items packed and sealed, ready for rider pickup

            - `RIDER_ASSIGNED`: A rider has been assigned and is heading to the store

            - `OUT_FOR_DELIVERY`: Rider has picked up the order and is en route

            - `DELIVERED`: Order successfully handed to the customer

            - `FAILED`: Order failed due to payment or inventory error

            - `CANCELLED`: Order was cancelled by the customer or system

            '
          enum:
          - CART_LOCKED
          - PAYMENT_PENDING
          - PAYMENT_CONFIRMED
          - INVENTORY_RESERVED
          - PICKING
          - PACKED
          - RIDER_ASSIGNED
          - OUT_FOR_DELIVERY
          - DELIVERED
          - FAILED
          - CANCELLED
          example: RIDER_ASSIGNED
        store_id:
          type: string
          description: Identifier of the dark store fulfilling the order.
          example: store-mum-andheri-01
        items:
          type: array
          description: Itemised breakdown of the order.
          items:
            $ref: '#/components/schemas/OrderItemResponse'
        total_amount:
          type: number
          format: double
          description: Total charged amount for the order (inclusive of taxes and delivery fee).
          example: 101.0
        currency:
          type: string
          description: ISO 4217 currency code.
          default: INR
          example: INR
        eta_minutes:
          type: integer
          nullable: true
          description: 'Estimated delivery time in minutes from order placement. Null once

            the order has been delivered, failed, or cancelled.

            '
          example: 12
        rider:
          nullable: true
          description: 'Rider details, populated once a rider is assigned. Null before

            `RIDER_ASSIGNED` status and after `DELIVERED`.

            '
          allOf:
          - $ref: '#/components/schemas/RiderSummary'
        created_at:
          type: string
          format: date-time
          description: ISO 8601 timestamp of when the order was placed.
          example: '2026-02-22T09:15:00Z'
        updated_at:
          type: string
          format: date-time
          description: ISO 8601 timestamp of the most recent status change.
          example: '2026-02-22T09:21:10Z'
    OrderListResponse:
      type: object
      description: Paginated list of orders for the authenticated user.
      required:
      - items
      - total
      properties:
        items:
          type: array
          description: Orders in the current page, ordered by `created_at` descending.
          items:
            $ref: '#/components/schemas/OrderResponse'
        next_cursor:
          type: string
          nullable: true
          description: 'Opaque cursor to pass as the `cursor` query parameter on the next

            request to retrieve the following page. Null when this is the last page.

            '
          example: eyJvcmRlcl9pZCI6Im9yZC01NTBlODQwMCIsInRzIjoiMjAyNi0wMi0yMlQwOToxNTowMFoifQ==
        total:
          type: integer
          description: Total number of orders across all pages for this user.
          example: 47
    OrderItemResponse:
      type: object
      description: A single fulfilled line-item within an order response.
      required:
      - sku_id
      - name
      - qty
      - unit_price
      - total_price
      properties:
        sku_id:
          type: string
          description: Stock Keeping Unit identifier.
          example: SKU-AMUL-MILK-500ML
        name:
          type: string
          description: Human-readable product name at the time of order.
          example: Amul Taaza Toned Milk 500ml
        qty:
          type: integer
          description: Quantity ordered.
          minimum: 1
          example: 2
        unit_price:
          type: number
          format: double
          description: Price per unit in the order currency at the time of order placement.
          example: 28.0
        total_price:
          type: number
          format: double
          description: Line-item total (unit_price × qty).
          example: 56.0
        image_url:
          type: string
          format: uri
          nullable: true
          description: CDN URL of the product image. Null if no image is available.
          example: https://cdn.grocery.internal/images/SKU-AMUL-MILK-500ML.jpg
    RiderSummary:
      type: object
      description: Abbreviated rider profile attached to an order once assigned.
      required:
      - rider_id
      - name
      - phone_masked
      - vehicle_type
      properties:
        rider_id:
          type: string
          description: Unique identifier for the rider.
          example: rider-8821
        name:
          type: string
          description: Rider's first name.
          example: Ravi Kumar
        phone_masked:
          type: string
          description: 'Rider''s phone number with all but the last 4 digits masked with

            asterisks, e.g., `******7654`. Used to enable in-app calling

            without exposing the full number.

            '
          pattern: ^\*{6}\d{4}$
          example: '******7654'
        vehicle_type:
          type: string
          description: Type of vehicle the rider is operating.
          enum:
          - BIKE
          - CYCLE
          - EV_BIKE
          example: BIKE
    TrackingResponse:
      type: object
      description: Real-time delivery tracking data for an order that is out for delivery.
      required:
      - rider_name
      - phone_masked
      - lat
      - lng
      - eta_minutes_remaining
      - status
      properties:
        rider_name:
          type: string
          description: Rider's display name.
          example: Ravi Kumar
        phone_masked:
          type: string
          description: Rider's phone number with all but the last 4 digits masked.
          pattern: ^\*{6}\d{4}$
          example: '******7654'
        lat:
          type: number
          format: double
          description: Rider's current latitude (WGS 84), updated every 10 seconds.
          minimum: -90
          maximum: 90
          example: 19.11832
        lng:
          type: number
          format: double
          description: Rider's current longitude (WGS 84), updated every 10 seconds.
          minimum: -180
          maximum: 180
          example: 72.84621
        eta_minutes_remaining:
          type: integer
          description: Estimated minutes until the rider reaches the delivery address.
          minimum: 0
          example: 4
        status:
          type: string
          description: Order status at the time of the tracking snapshot.
          enum:
          - OUT_FOR_DELIVERY
          - DELIVERED
          example: OUT_FOR_DELIVERY
    LoginRequest:
      type: object
      description: Request body to initiate the OTP login flow.
      required:
      - phone_number
      properties:
        phone_number:
          type: string
          description: 'Customer''s mobile number in E.164 format. Must include country code

            (e.g., +91 for India). Used to deliver the OTP via SMS.

            '
          pattern: ^\+[1-9]\d{7,14}$
          example: '+919876543210'
    OTPSentResponse:
      type: object
      description: Confirmation that an OTP has been dispatched to the phone number.
      required:
      - message
      - expires_in_seconds
      properties:
        message:
          type: string
          description: Human-readable confirmation message (safe to display in UI).
          example: OTP sent to +919876543210
        expires_in_seconds:
          type: integer
          description: Number of seconds the OTP remains valid before expiring.
          minimum: 60
          maximum: 600
          example: 300
    OTPVerifyRequest:
      type: object
      description: Request body to verify an OTP and obtain authentication tokens.
      required:
      - phone_number
      - otp
      properties:
        phone_number:
          type: string
          description: The phone number to which the OTP was sent, in E.164 format.
          pattern: ^\+[1-9]\d{7,14}$
          example: '+919876543210'
        otp:
          type: string
          description: The 6-digit one-time password received via SMS.
          pattern: ^\d{6}$
          minLength: 6
          maxLength: 6
          example: '482917'
    AuthResponse:
      type: object
      description: Authentication token pair returned on successful login or token refresh.
      required:
      - access_token
      - refresh_token
      - expires_in
      - user_id
      properties:
        access_token:
          type: string
          description: 'Short-lived JWT access token to be sent as `Authorization: Bearer <token>`

            on authenticated API requests. Expires in `expires_in` seconds.

            '
          example: eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c3ItYTFiMmMzZDQiLCJwaG9uZSI6Iis5MTk4NzY1NDMyMTAiLCJpYXQiOjE3NDA2NDE0MDAsImV4cCI6MTc0MDY0NTAwMH0.signature
        refresh_token:
          type: string
          description: 'Long-lived opaque refresh token used to obtain a new access token via

            `POST /auth/refresh`. Rotated on every use. Store securely (HTTP-only

            cookie or secure storage).

            '
          example: rt-8f4e2a1b9d7c6e3f0a5b2d8e1c4f7a9b
        expires_in:
          type: integer
          description: Lifetime of the `access_token` in seconds.
          example: 3600
        user_id:
          type: string
          description: Unique identifier of the authenticated user.
          example: usr-a1b2c3d4
    RefreshRequest:
      type: object
      description: Request body to exchange a refresh token for a new access token.
      required:
      - refresh_token
      properties:
        refresh_token:
          type: string
          description: The refresh token previously issued by `POST /auth/verify-otp` or `POST /auth/refresh`.
          example: rt-8f4e2a1b9d7c6e3f0a5b2d8e1c4f7a9b
    UserProfile:
      type: object
      description: Public profile of an authenticated user.
      required:
      - user_id
      - phone_number
      - created_at
      properties:
        user_id:
          type: string
          description: Unique identifier for the user.
          example: usr-a1b2c3d4
        name:
          type: string
          nullable: true
          description: User's display name. Null if not yet set (e.g., new user).
          example: Priya Sharma
        phone_number:
          type: string
          description: Verified mobile number in E.164 format. Cannot be changed after registration.
          pattern: ^\+[1-9]\d{7,14}$
          example: '+919876543210'
        email:
          type: string
          format: email
          nullable: true
          description: Optional email address. Null if not provided.
          example: priya.sharma@example.com
        created_at:
          type: string
          format: date-time
          description: ISO 8601 timestamp of when the user account was created.
          example: '2025-08-15T10:22:00Z'
    Address:
      type: object
      description: A saved delivery address associated with a user account.
      required:
      - address_id
      - label
      - line1
      - city
      - pincode
      - lat
      - lng
      - is_default
      properties:
        address_id:
          type: string
          description: Unique identifier for the saved address.
          example: addr-7f3a2b1c
        label:
          type: string
          description: Semantic label to help the user identify the address.
          enum:
          - HOME
          - WORK
          - OTHER
          example: HOME
        line1:
          type: string
          description: Primary address line (flat/house number, building name, street).
          maxLength: 255
          example: Flat 4B, Anand Nagar CHS
        line2:
          type: string
          nullable: true
          description: Secondary address line (landmark, locality). Optional.
          maxLength: 255
          example: Near Lokhandwala Market
        city:
          type: string
          description: City name.
          maxLength: 100
          example: Mumbai
        pincode:
          type: string
          description: Postal/ZIP code (6-digit Indian PIN code).
          pattern: ^\d{6}$
          example: '400053'
        lat:
          type: number
          format: double
          description: Latitude of the delivery location (WGS 84).
          minimum: -90
          maximum: 90
          example: 19.13621
        lng:
          type: number
          format: double
          description: Longitude of the delivery location (WGS 84).
          minimum: -180
          maximum: 180
          example: 72.83507
        is_default:
          type: boolean
          description: Whether this is the user's default delivery address.
          example: true
    AddressRequest:
      type: object
      description: Request body for creating a new saved delivery address.
      required:
      - label
      - line1
      - city
      - pincode
      - lat
      - lng
      - is_default
      properties:
        label:
          type: string
          description: Semantic label to help the user identify the address.
          enum:
          - HOME
          - WORK
          - OTHER
          example: HOME
        line1:
          type: string
          description: Primary address line (flat/house number, building name, street).
          maxLength: 255
          example: Flat 4B, Anand Nagar CHS
        line2:
          type: string
          nullable: true
          description: Secondary address line (landmark, locality). Optional.
          maxLength: 255
          example: Near Lokhandwala Market
        city:
          type: string
          description: City name.
          maxLength: 100
          example: Mumbai
        pincode:
          type: string
          description: Postal/ZIP code (6-digit Indian PIN code).
          pattern: ^\d{6}$
          example: '400053'
        lat:
          type: number
          format: double
          description: Latitude of the delivery location (WGS 84).
          minimum: -90
          maximum: 90
          example: 19.13621
        lng:
          type: number
          format: double
          description: Longitude of the delivery location (WGS 84).
          minimum: -180
          maximum: 180
          example: 72.83507
        is_default:
          type: boolean
          description: 'Set to true to make this the default address. Any existing default

            address will be automatically demoted.

            '
          example: true
    ErrorResponse:
      type: object
      required:
      - code
      - message
      properties:
        code:
          type: string
          description: Machine-readable error code
          example: STORE_NOT_FOUND
        message:
          type: string
          description: Human-readable description of the error
          example: No store found with the provided ID
        details:
          type: object
          nullable: true
          additionalProperties: true
          description: Optional structured context providing additional error details
    ProductSummary:
      type: object
      description: Lightweight product representation used in list views, search results, and recommendation feeds.
      required:
      - sku_id
      - name
      - brand
      - category_id
      - category_name
      - price
      - unit
      - image_url
      - in_stock
      - tags
      properties:
        sku_id:
          type: string
          description: Unique Stock Keeping Unit identifier
          example: SKU-AMUL-BTR-500
        name:
          type: string
          description: Display name of the product
          example: Amul Butter
        brand:
          type: string
          description: Brand name of the product
          example: Amul
        category_id:
          type: string
          description: Identifier of the primary category this product belongs to
          example: dairy-and-eggs
        category_name:
          type: string
          description: Human-readable name of the primary category
          example: Dairy & Eggs
        price:
          type: number
          format: float
          description: Current selling price in INR
          example: 56.0
        original_price:
          type: number
          format: float
          nullable: true
          description: 'Original MRP before discount. Null if no discount is currently applied. When non-null, clients should
            display a strikethrough on this value.

            '
          example: 60.0
        unit:
          type: string
          description: Pack size or unit description shown to the customer
          example: 500g
        image_url:
          type: string
          format: uri
          description: URL to the primary product thumbnail image (WebP preferred)
          example: https://cdn.groceryapp.example/images/SKU-AMUL-BTR-500.webp
        in_stock:
          type: boolean
          description: Whether the product is currently available at the requested store
          example: true
        stock_count:
          type: integer
          nullable: true
          description: 'Exact remaining stock count. Null when stock is greater than 10 — exact quantity is intentionally
            suppressed for UX to avoid anxiety-driven bulk buying.

            '
          example: 8
        tags:
          type: array
          description: Merchandising and discovery tags associated with the product
          items:
            type: string
          example:
          - organic
          - bestseller
    ProductDetail:
      type: object
      description: 'Full product detail including nutritional data, all images, and logistics metadata. Extends ProductSummary
        with additional fields.

        '
      required:
      - sku_id
      - name
      - brand
      - category_id
      - category_name
      - price
      - unit
      - image_url
      - in_stock
      - tags
      - description
      - images
      - weight_grams
      - nutritional_info
      - country_of_origin
      - is_sponsored
      properties:
        sku_id:
          type: string
          description: Unique Stock Keeping Unit identifier
          example: SKU-AMUL-BTR-500
        name:
          type: string
          description: Display name of the product
          example: Amul Butter
        brand:
          type: string
          description: Brand name of the product
          example: Amul
        category_id:
          type: string
          description: Identifier of the primary category
          example: dairy-and-eggs
        category_name:
          type: string
          description: Human-readable category name
          example: Dairy & Eggs
        price:
          type: number
          format: float
          description: Current selling price in INR
          example: 56.0
        original_price:
          type: number
          format: float
          nullable: true
          description: Original MRP before discount. Null if no discount is active.
          example: 60.0
        unit:
          type: string
          description: Pack size or unit description
          example: 500g
        image_url:
          type: string
          format: uri
          description: Primary product thumbnail image URL
          example: https://cdn.groceryapp.example/images/SKU-AMUL-BTR-500.webp
        in_stock:
          type: boolean
          description: Whether the product is in stock at the requested store
          example: true
        stock_count:
          type: integer
          nullable: true
          description: Exact stock count, null when greater than 10 for UX reasons.
          example: 8
        tags:
          type: array
          description: Merchandising and discovery tags
          items:
            type: string
          example:
          - bestseller
        description:
          type: string
          description: Long-form product description shown on the detail page
          example: Amul Butter is pasteurised butter made from fresh cream. Rich in vitamins A, D, and E. Made without artificial
            preservatives.
        images:
          type: array
          description: 'Ordered list of full-resolution product image URLs. First item matches image_url. Clients should display
            as a swipeable gallery.

            '
          items:
            type: string
            format: uri
          example:
          - https://cdn.groceryapp.example/images/SKU-AMUL-BTR-500.webp
          - https://cdn.groceryapp.example/images/SKU-AMUL-BTR-500-back.webp
          - https://cdn.groceryapp.example/images/SKU-AMUL-BTR-500-nutrition.webp
        weight_grams:
          type: integer
          description: Net weight of the product in grams — used for logistics weight calculations
          example: 500
        nutritional_info:
          type: object
          nullable: false
          description: 'Per-100g nutritional breakdown. Individual fields are nullable when the manufacturer has not disclosed
            that value.

            '
          properties:
            calories:
              type: number
              format: float
              nullable: true
              description: Energy value in kcal per 100g
              example: 717
            protein:
              type: number
              format: float
              nullable: true
              description: Protein content in grams per 100g
              example: 0.9
            carbs:
              type: number
              format: float
              nullable: true
              description: Carbohydrate content in grams per 100g
              example: 0.1
            fat:
              type: number
              format: float
              nullable: true
              description: Total fat content in grams per 100g
              example: 81.0
        manufacturer:
          type: string
          nullable: true
          description: Legal name of the manufacturer. Null if not disclosed by the brand.
          example: Gujarat Cooperative Milk Marketing Federation Ltd.
        country_of_origin:
          type: string
          description: ISO country name or code indicating where the product was manufactured
          example: India
        shelf_life_days:
          type: integer
          nullable: true
          description: Shelf life in days from manufacturing date. Null if not applicable (e.g. fresh produce).
          example: 90
        is_sponsored:
          type: boolean
          description: Whether this product placement is a paid sponsorship. Must be disclosed to the user per advertising
            guidelines.
          example: false
    SearchResponse:
      type: object
      description: Response envelope for product search results.
      required:
      - query
      - items
      - total
      - took_ms
      - offset
      - limit
      properties:
        query:
          type: string
          description: The original search query string as received by the service
          example: amul butter
        items:
          type: array
          description: Page of matching products ordered by the requested sort
          items:
            $ref: '#/components/schemas/ProductSummary'
        total:
          type: integer
          description: Total number of matching products across all pages
          example: 47
        took_ms:
          type: integer
          description: 'Elasticsearch query latency in milliseconds. Exposed for client-side observability dashboards and
            SLA monitoring.

            '
          example: 43
        offset:
          type: integer
          description: The offset value used for this page
          example: 0
        limit:
          type: integer
          description: The limit value used for this page
          example: 20
    AutocompleteResponse:
      type: object
      description: Response envelope for type-ahead autocomplete suggestions.
      required:
      - suggestions
      - query
      properties:
        suggestions:
          type: array
          description: Ordered list of suggestion strings. Ordered by search popularity at the store.
          items:
            type: string
          example:
          - amul butter
          - amul milk
          - amul paneer
          - amul cheese
          - amul curd
        query:
          type: string
          description: The partial query string that was used to generate these suggestions
          example: am
    Category:
      type: object
      description: 'A product category node. Categories are hierarchical — a top-level category may contain subcategories.
        Subcategories themselves may contain further nesting (recursive schema).

        '
      required:
      - category_id
      - name
      - slug
      - product_count
      properties:
        category_id:
          type: string
          description: Unique identifier for the category
          example: dairy-and-eggs
        name:
          type: string
          description: Human-readable display name
          example: Dairy & Eggs
        slug:
          type: string
          description: URL-safe slug for use in deep links and routing
          example: dairy-and-eggs
        icon_url:
          type: string
          format: uri
          nullable: true
          description: URL to the category icon. Null for subcategories that do not have a dedicated icon.
          example: https://cdn.groceryapp.example/icons/dairy.svg
        product_count:
          type: integer
          description: Total number of active products in this category (including subcategories)
          example: 142
        subcategories:
          type: array
          nullable: true
          description: 'Child categories under this node. Null when this is a leaf category with no further subdivision.

            '
          items:
            $ref: '#/components/schemas/Category'
          example:
          - category_id: butter-and-ghee
            name: Butter & Ghee
            slug: butter-and-ghee
            icon_url: null
            product_count: 23
            subcategories: null
    ProductListResponse:
      type: object
      description: Response envelope for category browse listings.
      required:
      - items
      - total
      - category
      - offset
      - limit
      properties:
        items:
          type: array
          description: Page of products in this category ordered by the requested sort
          items:
            $ref: '#/components/schemas/ProductSummary'
        total:
          type: integer
          description: Total number of products in this category across all pages
          example: 142
        category:
          $ref: '#/components/schemas/Category'
          description: Metadata of the category being browsed
        offset:
          type: integer
          description: The offset value used for this page
          example: 0
        limit:
          type: integer
          description: The limit value used for this page
          example: 40
    RecommendationResponse:
      type: object
      description: Response envelope for personalised or editorial recommendation feeds.
      required:
      - items
      - section
      - is_personalised
      - store_id
      properties:
        items:
          type: array
          description: Ordered list of recommended products. In-stock filtered at serve time.
          items:
            $ref: '#/components/schemas/ProductSummary'
        section:
          type: string
          description: The feed section for which recommendations were generated
          enum:
          - FOR_YOU
          - FREQUENTLY_BOUGHT
          - TRENDING
          - NEW_ARRIVALS
          example: FOR_YOU
        is_personalised:
          type: boolean
          description: 'True when the recommendations are user-specific (sufficient purchase history available). False for
            cold-start users who receive store-wide trending or editorial picks.

            '
          example: true
        store_id:
          type: string
          format: uuid
          description: The dark store UUID for which recommendations were resolved
          example: 3fa85f64-5717-4562-b3fc-2c963f66afa6
    SubstituteProductSummary:
      type: object
      description: 'A ProductSummary extended with a similarity_reason field indicating why this product was selected as a
        substitute.

        '
      required:
      - sku_id
      - name
      - brand
      - category_id
      - category_name
      - price
      - unit
      - image_url
      - in_stock
      - tags
      - similarity_reason
      properties:
        sku_id:
          type: string
          example: SKU-MOTHER-DAIRY-BTR-500
        name:
          type: string
          example: Mother Dairy Butter
        brand:
          type: string
          example: Mother Dairy
        category_id:
          type: string
          example: dairy-and-eggs
        category_name:
          type: string
          example: Dairy & Eggs
        price:
          type: number
          format: float
          example: 54.0
        original_price:
          type: number
          format: float
          nullable: true
          example: null
        unit:
          type: string
          example: 500g
        image_url:
          type: string
          format: uri
          example: https://cdn.groceryapp.example/images/SKU-MOTHER-DAIRY-BTR-500.webp
        in_stock:
          type: boolean
          example: true
        stock_count:
          type: integer
          nullable: true
          example: null
        tags:
          type: array
          items:
            type: string
          example: []
        similarity_reason:
          type: string
          description: 'Explains why this product was ranked as a substitute. SAME_BRAND_SAME_CATEGORY is preferred and ranked
            higher. DIFFERENT_BRAND_SAME_CATEGORY is used when no same-brand alternative is in stock.

            '
          enum:
          - SAME_BRAND_SAME_CATEGORY
          - DIFFERENT_BRAND_SAME_CATEGORY
          example: DIFFERENT_BRAND_SAME_CATEGORY
    SubstituteResponse:
      type: object
      description: Response envelope for out-of-stock substitute suggestions.
      required:
      - original_sku_id
      - substitutes
      properties:
        original_sku_id:
          type: string
          description: SKU identifier of the out-of-stock product for which substitutes are listed
          example: SKU-AMUL-BTR-500
        substitutes:
          type: array
          description: 'Ranked list of substitute products. Ordered by similarity score descending. SAME_BRAND_SAME_CATEGORY
            substitutes are always ranked above DIFFERENT_BRAND_SAME_CATEGORY.

            '
          items:
            $ref: '#/components/schemas/SubstituteProductSummary'
    StockItem:
      type: object
      required:
      - sku_id
      - qty_available
      - in_stock
      properties:
        sku_id:
          type: string
          description: Unique Stock Keeping Unit identifier
          example: SKU-001
        qty_available:
          type: integer
          minimum: 0
          description: Number of units currently available at the store
          example: 24
        in_stock:
          type: boolean
          description: True if qty_available > 0
          example: true
    StockCheckResponse:
      type: object
      required:
      - store_id
      - checked_at
      - items
      properties:
        store_id:
          type: string
          format: uuid
          description: ID of the store whose stock was checked
          example: a1b2c3d4-e5f6-7890-abcd-ef1234567890
        checked_at:
          type: string
          format: date-time
          description: Timestamp at which the stock snapshot was read
          example: '2026-02-22T10:15:00Z'
        items:
          type: array
          items:
            $ref: '#/components/schemas/StockItem'
    RestockRequestItem:
      type: object
      required:
      - sku_id
      - qty_added
      properties:
        sku_id:
          type: string
          description: SKU identifier of the item being restocked
          example: SKU-001
        qty_added:
          type: integer
          minimum: 1
          description: Number of units being added to stock
          example: 50
        batch_id:
          type: string
          nullable: true
          description: Supplier batch reference, if applicable
          example: BATCH-2026-022-001
        expiry_date:
          type: string
          format: date
          nullable: true
          description: Expiry date of the restocked batch (ISO 8601 date)
          example: '2026-06-30'
    RestockRequest:
      type: object
      required:
      - items
      properties:
        items:
          type: array
          minItems: 1
          items:
            $ref: '#/components/schemas/RestockRequestItem'
    RestockResponseItem:
      type: object
      required:
      - sku_id
      - new_qty_available
      - updated_at
      properties:
        sku_id:
          type: string
          example: SKU-001
        new_qty_available:
          type: integer
          minimum: 0
          description: Total available quantity after restocking
          example: 74
        updated_at:
          type: string
          format: date-time
          description: Timestamp when the Redis and eventual PG records were updated
          example: '2026-02-22T10:20:00Z'
    RestockResponse:
      type: object
      required:
      - store_id
      - items
      properties:
        store_id:
          type: string
          format: uuid
          example: a1b2c3d4-e5f6-7890-abcd-ef1234567890
        items:
          type: array
          items:
            $ref: '#/components/schemas/RestockResponseItem'
    AdjustmentReason:
      type: string
      enum:
      - SPOILAGE
      - DAMAGE
      - THEFT
      - EXPIRED
      - COUNT_CORRECTION
      description: Reason for inventory adjustment
      example: SPOILAGE
    AdjustmentRequestItem:
      type: object
      required:
      - sku_id
      - qty_change
      - reason
      properties:
        sku_id:
          type: string
          description: SKU identifier of the item being adjusted
          example: SKU-005
        qty_change:
          type: integer
          description: 'Delta to apply to current stock. Negative values reduce stock (write-off). Positive values are not
            permitted through this endpoint; use /restock instead.

            '
          example: -3
        reason:
          $ref: '#/components/schemas/AdjustmentReason'
    AdjustmentRequest:
      type: object
      required:
      - items
      properties:
        items:
          type: array
          minItems: 1
          items:
            $ref: '#/components/schemas/AdjustmentRequestItem'
    AdjustmentResponseItem:
      type: object
      required:
      - sku_id
      - previous_qty
      - new_qty
      - reason
      - adjusted_at
      properties:
        sku_id:
          type: string
          example: SKU-005
        previous_qty:
          type: integer
          minimum: 0
          description: Quantity on hand before this adjustment
          example: 12
        new_qty:
          type: integer
          minimum: 0
          description: Quantity on hand after this adjustment
          example: 9
        reason:
          $ref: '#/components/schemas/AdjustmentReason'
        adjusted_at:
          type: string
          format: date-time
          example: '2026-02-22T11:00:00Z'
    AdjustmentResponse:
      type: object
      required:
      - store_id
      - items
      properties:
        store_id:
          type: string
          format: uuid
          example: a1b2c3d4-e5f6-7890-abcd-ef1234567890
        items:
          type: array
          items:
            $ref: '#/components/schemas/AdjustmentResponseItem'
    LowStockItem:
      type: object
      required:
      - sku_id
      - name
      - current_qty
      - threshold
      properties:
        sku_id:
          type: string
          example: SKU-012
        name:
          type: string
          description: Human-readable product name
          example: Organic Whole Milk 1L
        current_qty:
          type: integer
          minimum: 0
          example: 2
        threshold:
          type: integer
          minimum: 1
          description: Reorder threshold quantity configured for this SKU at this store
          example: 5
        last_restocked_at:
          type: string
          format: date-time
          nullable: true
          description: Timestamp of the last restock event; null if never restocked
          example: '2026-02-21T08:30:00Z'
    LowStockResponse:
      type: object
      required:
      - store_id
      - items
      properties:
        store_id:
          type: string
          format: uuid
          example: a1b2c3d4-e5f6-7890-abcd-ef1234567890
        items:
          type: array
          items:
            $ref: '#/components/schemas/LowStockItem'
    RiderStatus:
      type: string
      enum:
      - AVAILABLE
      - ON_DELIVERY
      - OFFLINE
      - STALE_GPS
      description: Current operational status of the rider
      example: AVAILABLE
    VehicleType:
      type: string
      enum:
      - BIKE
      - CYCLE
      - EV_BIKE
      description: Type of vehicle the rider uses for deliveries
      example: BIKE
    RiderLocation:
      type: object
      required:
      - rider_id
      - name
      - lat
      - lng
      - distance_km
      - status
      - active_deliveries
      properties:
        rider_id:
          type: string
          format: uuid
          example: r1b2c3d4-e5f6-7890-abcd-ef1234567891
        name:
          type: string
          example: Arjun Sharma
        lat:
          type: number
          format: double
          minimum: -90
          maximum: 90
          description: Current latitude of the rider
          example: 12.972
        lng:
          type: number
          format: double
          minimum: -180
          maximum: 180
          description: Current longitude of the rider
          example: 77.595
        distance_km:
          type: number
          format: double
          minimum: 0
          description: Distance from the query origin to the rider, in kilometres
          example: 0.3
        status:
          $ref: '#/components/schemas/RiderStatus'
        active_deliveries:
          type: integer
          minimum: 0
          description: Number of active deliveries currently assigned to this rider
          example: 0
    NearbyRidersResponse:
      type: object
      required:
      - riders
      - total
      - radius_km
      properties:
        riders:
          type: array
          items:
            $ref: '#/components/schemas/RiderLocation'
        total:
          type: integer
          minimum: 0
          description: Total number of riders found within the specified radius
          example: 2
        radius_km:
          type: number
          format: double
          description: Effective radius used for the search
          example: 3.0
    LocationUpdateRequest:
      type: object
      required:
      - lat
      - lng
      - timestamp
      properties:
        lat:
          type: number
          format: double
          minimum: -90
          maximum: 90
          description: Latitude of the rider's current position
          example: 12.9725
        lng:
          type: number
          format: double
          minimum: -180
          maximum: 180
          description: Longitude of the rider's current position
          example: 77.5952
        accuracy_meters:
          type: number
          format: double
          nullable: true
          minimum: 0
          description: GPS accuracy radius reported by the device (metres)
          example: 8.5
        timestamp:
          type: string
          format: date-time
          description: Device-side UTC timestamp when the GPS fix was captured
          example: '2026-02-22T10:30:00Z'
    LastLocation:
      type: object
      required:
      - lat
      - lng
      - updated_at
      properties:
        lat:
          type: number
          format: double
          minimum: -90
          maximum: 90
          example: 12.9722
        lng:
          type: number
          format: double
          minimum: -180
          maximum: 180
          example: 77.5948
        updated_at:
          type: string
          format: date-time
          example: '2026-02-22T10:29:55Z'
    RiderStatusResponse:
      type: object
      required:
      - rider_id
      - name
      - status
      - vehicle_type
      properties:
        rider_id:
          type: string
          format: uuid
          example: r1b2c3d4-e5f6-7890-abcd-ef1234567891
        name:
          type: string
          example: Arjun Sharma
        status:
          $ref: '#/components/schemas/RiderStatus'
        current_order_id:
          type: string
          format: uuid
          nullable: true
          description: ID of the order currently assigned to this rider; null if unassigned
          example: ord-9a8b7c6d-e5f4-3210-fedc-ba9876543210
        last_location:
          allOf:
          - $ref: '#/components/schemas/LastLocation'
          nullable: true
          description: Most recent known GPS position; null if the rider has never sent a location ping
        vehicle_type:
          $ref: '#/components/schemas/VehicleType'
    AcceptOrderRequest:
      type: object
      required:
      - order_id
      properties:
        order_id:
          type: string
          format: uuid
          description: ID of the order the rider wants to accept
          example: ord-9a8b7c6d-e5f4-3210-fedc-ba9876543210
    AcceptOrderResponse:
      type: object
      required:
      - order_id
      - store_address
      - customer_address
      - items_count
      - estimated_pick_time_minutes
      properties:
        order_id:
          type: string
          format: uuid
          example: ord-9a8b7c6d-e5f4-3210-fedc-ba9876543210
        store_address:
          type: string
          description: Full street address of the dark store for pickup
          example: 42 MG Road, Indiranagar, Bengaluru 560038
        customer_address:
          type: string
          description: Full delivery address for the customer
          example: 15/A, 3rd Cross, HSR Layout Sector 2, Bengaluru 560102
        items_count:
          type: integer
          minimum: 1
          description: Number of line items in the order to be picked and delivered
          example: 7
        estimated_pick_time_minutes:
          type: integer
          minimum: 0
          description: Estimated time for the store picker to have the order ready for handoff
          example: 4
    RiderStatusUpdateRequest:
      type: object
      required:
      - status
      properties:
        status:
          type: string
          enum:
          - AVAILABLE
          - OFFLINE
          description: Desired availability status for the rider
          example: AVAILABLE
    StoreCongestionLevel:
      type: string
      enum:
      - LOW
      - MEDIUM
      - HIGH
      description: Qualitative congestion level at a dark store based on active orders vs. picker capacity
      example: LOW
    PreCheckoutETAResponse:
      type: object
      required:
      - eta_minutes
      - eta_min
      - eta_max
      - store_congestion
      properties:
        eta_minutes:
          type: integer
          minimum: 0
          description: Best-estimate delivery time in minutes from order placement
          example: 18
        eta_min:
          type: integer
          minimum: 0
          description: Optimistic lower bound of delivery window (minutes)
          example: 15
        eta_max:
          type: integer
          minimum: 0
          description: Pessimistic upper bound of delivery window (minutes)
          example: 22
        store_congestion:
          $ref: '#/components/schemas/StoreCongestionLevel'
        disclaimer:
          type: string
          nullable: true
          description: Optional human-readable caveat displayed to the customer (e.g. demand surge notice)
          example: Slightly delayed due to high demand
    ETABreakdown:
      type: object
      required:
      - t_pick_minutes
      properties:
        t_pick_minutes:
          type: integer
          minimum: 0
          description: Estimated time for store pickers to assemble the order
          example: 5
        t_wait_minutes:
          type: integer
          nullable: true
          minimum: 0
          description: 'Estimated time a rider waits at the store for the order to be ready; null before a rider has been
            assigned.

            '
          example: 2
        t_travel_minutes:
          type: integer
          nullable: true
          minimum: 0
          description: 'Estimated rider travel time from store to customer door; null before a rider has been assigned.

            '
          example: 9
    OrderETAPhase:
      type: string
      enum:
      - PREPARING
      - RIDER_COMING
      - OUT_FOR_DELIVERY
      description: 'Current phase of the order fulfillment pipeline. PREPARING: items being picked. RIDER_COMING: rider en
        route to store. OUT_FOR_DELIVERY: rider has picked up and is heading to customer.

        '
      example: OUT_FOR_DELIVERY
    OrderETAResponse:
      type: object
      required:
      - order_id
      - eta_minutes_remaining
      - phase
      - last_updated_at
      - breakdown
      properties:
        order_id:
          type: string
          format: uuid
          example: ord-9a8b7c6d-e5f4-3210-fedc-ba9876543210
        eta_minutes_remaining:
          type: integer
          minimum: 0
          description: Minutes remaining until expected delivery at customer door
          example: 11
        phase:
          $ref: '#/components/schemas/OrderETAPhase'
        last_updated_at:
          type: string
          format: date-time
          description: Timestamp when this ETA estimate was last recalculated
          example: '2026-02-22T10:45:00Z'
        breakdown:
          $ref: '#/components/schemas/ETABreakdown'
    StoreETA:
      type: object
      required:
      - store_id
      - name
      - address
      - distance_km
      - eta_minutes
      - congestion_level
      - is_available
      properties:
        store_id:
          type: string
          format: uuid
          example: a1b2c3d4-e5f6-7890-abcd-ef1234567890
        name:
          type: string
          description: Human-readable store name
          example: Indiranagar Dark Store
        address:
          type: string
          description: Full street address of the dark store
          example: 42 MG Road, Indiranagar, Bengaluru 560038
        distance_km:
          type: number
          format: double
          minimum: 0
          description: Straight-line distance from the query location to this store (km)
          example: 1.4
        eta_minutes:
          type: integer
          minimum: 0
          description: Estimated total delivery time if ordering from this store right now
          example: 14
        congestion_level:
          $ref: '#/components/schemas/StoreCongestionLevel'
        is_available:
          type: boolean
          description: 'False if the store is closed, at max capacity, or has no active riders in the vicinity; otherwise
            true.

            '
          example: true
    StoreETAListResponse:
      type: object
      required:
      - stores
      - location
      properties:
        stores:
          type: array
          items:
            $ref: '#/components/schemas/StoreETA'
          description: Dark stores within the requested radius, ordered by ETA ascending
        location:
          type: object
          required:
          - lat
          - lng
          description: The customer location used as the origin for the search
          properties:
            lat:
              type: number
              format: double
              minimum: -90
              maximum: 90
              example: 12.915
            lng:
              type: number
              format: double
              minimum: -180
              maximum: 180
              example: 77.6229
```
