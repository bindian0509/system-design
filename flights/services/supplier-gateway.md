# Supplier Gateway Service

## Overview

The Supplier Gateway provides a unified interface to 500+ external flight data sources including Global Distribution Systems (GDS), direct airline APIs, Low-Cost Carrier (LCC) aggregators, and regional providers. It abstracts away the complexity of different protocols, data formats, and authentication mechanisms.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Supplier Gateway Service                             │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                        Request Router                                 │   │
│  │    (Route requests to appropriate adapter based on supplier code)    │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│       ┌────────────────────────────┼────────────────────────────┐           │
│       ▼                            ▼                            ▼           │
│  ┌──────────┐               ┌──────────┐               ┌──────────┐        │
│  │   GDS    │               │  Direct  │               │   LCC    │        │
│  │ Adapters │               │ Airlines │               │ Adapters │        │
│  │          │               │ Adapters │               │          │        │
│  │┌────────┐│               │┌────────┐│               │┌────────┐│        │
│  ││Amadeus ││               ││ United ││               ││ Spirit ││        │
│  │└────────┘│               │└────────┘│               │└────────┘│        │
│  │┌────────┐│               │┌────────┐│               │┌────────┐│        │
│  ││ Sabre  ││               ││ Delta  ││               ││Frontier││        │
│  │└────────┘│               │└────────┘│               │└────────┘│        │
│  │┌────────┐│               │┌────────┐│               │┌────────┐│        │
│  ││Travelp.││               ││   AA   ││               ││ Ryanair││        │
│  │└────────┘│               │└────────┘│               │└────────┘│        │
│  └──────────┘               └──────────┘               └──────────┘        │
│       │                            │                            │           │
│       └────────────────────────────┼────────────────────────────┘           │
│                                    ▼                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                     Resilience Layer                                  │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────┐ │   │
│  │  │   Circuit    │  │   Bulkhead   │  │    Retry     │  │  Rate    │ │   │
│  │  │   Breaker    │  │  (Isolation) │  │   Handler    │  │ Limiter  │ │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └──────────┘ │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    Response Normalizer                                │   │
│  │         (Convert supplier-specific formats to unified schema)         │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                      Metrics & Logging                                │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Supplier Categories

### 1. Global Distribution Systems (GDS)

| GDS | Coverage | Protocol | Typical Latency |
|-----|----------|----------|-----------------|
| Amadeus | Global, 450+ airlines | XML/SOAP, REST | 1-3s |
| Sabre | North America focus, 400+ airlines | XML/SOAP | 1-3s |
| Travelport (Galileo/Apollo/Worldspan) | Global | XML/SOAP | 1-3s |

**GDS Characteristics:**
- Comprehensive inventory across multiple airlines
- Complex fare rules and ticketing
- Session-based authentication
- Metered pricing (per-transaction fees)

### 2. Direct Airline APIs

| Airline | API Type | Protocol | Typical Latency |
|---------|----------|----------|-----------------|
| United | NDC | REST/JSON | 500ms-1.5s |
| Delta | Proprietary | REST/JSON | 500ms-1.5s |
| American | NDC | REST/JSON | 500ms-1.5s |
| Southwest | Proprietary | REST/JSON | 1-2s |
| JetBlue | NDC | REST/JSON | 500ms-1.5s |

**Direct API Characteristics:**
- Most accurate availability
- Direct pricing (no markup from GDS)
- Often better for ancillary products
- Requires individual integration per airline

### 3. Low-Cost Carrier (LCC) Aggregators

| Provider | Coverage | Protocol |
|----------|----------|----------|
| Kiwi.com | LCC worldwide | REST/JSON |
| Duffel | Multi-source | REST/JSON |
| Skypicker | European LCCs | REST/JSON |

### 4. Regional Providers

| Provider | Region | Airlines |
|----------|--------|----------|
| TBO | Asia | 50+ |
| Mystifly | Middle East/Africa | 80+ |
| AeroCRS | Regional carriers | 100+ |

---

## Adapter Interface

All adapters implement a common interface:

```go
type SupplierAdapter interface {
    // Search for flights
    Search(ctx context.Context, req *SearchRequest) (*SupplierResponse, error)

    // Verify price and availability
    Verify(ctx context.Context, flightID string) (*VerifyResponse, error)

    // Book a flight
    Book(ctx context.Context, req *BookingRequest) (*BookingResponse, error)

    // Cancel a booking
    Cancel(ctx context.Context, bookingRef string) (*CancelResponse, error)

    // Get supplier metadata
    GetMetadata() SupplierMetadata
}

type SupplierMetadata struct {
    Code             string
    Name             string
    Type             string   // gds, direct, lcc, regional
    SupportedRoutes  []Route
    AverageLatencyMs int
    TimeoutMs        int
    RateLimitPerMin  int
}
```

---

## Adapter Implementation Example: Amadeus

```go
type AmadeusAdapter struct {
    client     *http.Client
    baseURL    string
    apiKey     string
    apiSecret  string
    tokenMgr   *TokenManager
    config     AmadeusConfig
}

func NewAmadeusAdapter(config AmadeusConfig) *AmadeusAdapter {
    return &AmadeusAdapter{
        client: &http.Client{
            Timeout: time.Duration(config.TimeoutMs) * time.Millisecond,
            Transport: &http.Transport{
                MaxIdleConns:        100,
                MaxIdleConnsPerHost: 100,
                IdleConnTimeout:     90 * time.Second,
            },
        },
        baseURL:   config.BaseURL,
        apiKey:    config.APIKey,
        apiSecret: config.APISecret,
        tokenMgr:  NewTokenManager(config),
        config:    config,
    }
}

func (a *AmadeusAdapter) Search(ctx context.Context, req *SearchRequest) (*SupplierResponse, error) {
    // Get OAuth token
    token, err := a.tokenMgr.GetToken(ctx)
    if err != nil {
        return nil, fmt.Errorf("failed to get token: %w", err)
    }

    // Build Amadeus-specific request
    amadeusReq := a.buildSearchRequest(req)

    // Marshal to JSON
    body, err := json.Marshal(amadeusReq)
    if err != nil {
        return nil, fmt.Errorf("failed to marshal request: %w", err)
    }

    // Create HTTP request
    httpReq, err := http.NewRequestWithContext(
        ctx,
        "POST",
        a.baseURL+"/v2/shopping/flight-offers",
        bytes.NewReader(body),
    )
    if err != nil {
        return nil, err
    }

    httpReq.Header.Set("Authorization", "Bearer "+token)
    httpReq.Header.Set("Content-Type", "application/json")

    // Execute request
    resp, err := a.client.Do(httpReq)
    if err != nil {
        return nil, fmt.Errorf("request failed: %w", err)
    }
    defer resp.Body.Close()

    // Handle response
    if resp.StatusCode != http.StatusOK {
        return nil, a.handleError(resp)
    }

    // Parse response
    var amadeusResp AmadeusFlightOffersResponse
    if err := json.NewDecoder(resp.Body).Decode(&amadeusResp); err != nil {
        return nil, fmt.Errorf("failed to decode response: %w", err)
    }

    // Normalize to unified format
    return a.normalizeResponse(amadeusResp), nil
}

func (a *AmadeusAdapter) buildSearchRequest(req *SearchRequest) AmadeusSearchRequest {
    return AmadeusSearchRequest{
        CurrencyCode: "USD",
        OriginDestinations: []AmadeusOriginDestination{
            {
                ID:                    "1",
                OriginLocationCode:    req.Origin,
                DestinationLocationCode: req.Destination,
                DepartureDateTimeRange: AmadeusDateTimeRange{
                    Date: req.DepartureDate,
                },
            },
        },
        Travelers: a.buildTravelers(req),
        Sources:   []string{"GDS"},
        SearchCriteria: AmadeusSearchCriteria{
            MaxFlightOffers:      100,
            FlightFilters: AmadeusFlightFilters{
                CabinRestrictions: []AmadeusCabinRestriction{
                    {
                        Cabin: mapCabinClass(req.CabinClass),
                        Coverage: "MOST_SEGMENTS",
                        OriginDestinationIds: []string{"1"},
                    },
                },
            },
        },
    }
}

func (a *AmadeusAdapter) normalizeResponse(resp AmadeusFlightOffersResponse) *SupplierResponse {
    flights := make([]Flight, 0, len(resp.Data))

    for _, offer := range resp.Data {
        flight := Flight{
            FlightID:     fmt.Sprintf("amadeus_%s", offer.ID),
            SupplierCode: "amadeus",
            Segments:     a.normalizeSegments(offer.Itineraries),
            Pricing:      a.normalizePricing(offer.Price),
            Availability: a.normalizeAvailability(offer),
        }
        flights = append(flights, flight)
    }

    return &SupplierResponse{
        Flights:   flights,
        Supplier:  "amadeus",
        Timestamp: time.Now(),
    }
}
```

---

## Resilience Patterns

### Circuit Breaker

Prevent cascading failures when a supplier is unhealthy:

```go
type CircuitBreaker struct {
    mu               sync.RWMutex
    state            CircuitState
    failures         int
    successes        int
    lastFailure      time.Time
    lastStateChange  time.Time
    config           CircuitBreakerConfig
}

type CircuitBreakerConfig struct {
    FailureThreshold   int           // Failures to open circuit
    SuccessThreshold   int           // Successes to close circuit
    Timeout            time.Duration // Time in open state before half-open
    HalfOpenMaxCalls   int           // Max calls in half-open state
}

type CircuitState int

const (
    StateClosed CircuitState = iota
    StateOpen
    StateHalfOpen
)

func (cb *CircuitBreaker) Execute(fn func() error) error {
    if !cb.canExecute() {
        return ErrCircuitOpen
    }

    err := fn()

    cb.recordResult(err)
    return err
}

func (cb *CircuitBreaker) canExecute() bool {
    cb.mu.RLock()
    defer cb.mu.RUnlock()

    switch cb.state {
    case StateClosed:
        return true
    case StateOpen:
        if time.Since(cb.lastStateChange) > cb.config.Timeout {
            cb.transitionTo(StateHalfOpen)
            return true
        }
        return false
    case StateHalfOpen:
        return cb.halfOpenCalls < cb.config.HalfOpenMaxCalls
    }
    return false
}

func (cb *CircuitBreaker) recordResult(err error) {
    cb.mu.Lock()
    defer cb.mu.Unlock()

    if err != nil {
        cb.failures++
        cb.successes = 0
        cb.lastFailure = time.Now()

        if cb.state == StateClosed && cb.failures >= cb.config.FailureThreshold {
            cb.transitionTo(StateOpen)
        } else if cb.state == StateHalfOpen {
            cb.transitionTo(StateOpen)
        }
    } else {
        cb.successes++
        cb.failures = 0

        if cb.state == StateHalfOpen && cb.successes >= cb.config.SuccessThreshold {
            cb.transitionTo(StateClosed)
        }
    }
}
```

### Bulkhead Pattern

Isolate suppliers to prevent one slow supplier from exhausting resources:

```go
type Bulkhead struct {
    semaphores map[string]chan struct{}
    configs    map[string]BulkheadConfig
}

type BulkheadConfig struct {
    MaxConcurrent int
    QueueSize     int
    Timeout       time.Duration
}

func NewBulkhead(configs map[string]BulkheadConfig) *Bulkhead {
    b := &Bulkhead{
        semaphores: make(map[string]chan struct{}),
        configs:    configs,
    }

    for supplier, config := range configs {
        b.semaphores[supplier] = make(chan struct{}, config.MaxConcurrent)
    }

    return b
}

func (b *Bulkhead) Execute(ctx context.Context, supplier string, fn func() error) error {
    config := b.configs[supplier]
    sem := b.semaphores[supplier]

    // Try to acquire semaphore
    select {
    case sem <- struct{}{}:
        defer func() { <-sem }()
        return fn()
    case <-time.After(config.Timeout):
        return ErrBulkheadFull
    case <-ctx.Done():
        return ctx.Err()
    }
}
```

**Default Bulkhead Configuration:**

| Supplier Type | Max Concurrent | Queue Size | Timeout |
|---------------|----------------|------------|---------|
| GDS | 50 | 100 | 5s |
| Direct Airlines | 100 | 200 | 3s |
| LCC | 30 | 50 | 5s |
| Regional | 20 | 30 | 10s |

### Retry Handler

```go
type RetryHandler struct {
    maxAttempts int
    baseDelay   time.Duration
    maxDelay    time.Duration
}

func (r *RetryHandler) Execute(ctx context.Context, fn func() error) error {
    var lastErr error

    for attempt := 0; attempt < r.maxAttempts; attempt++ {
        err := fn()
        if err == nil {
            return nil
        }

        if !r.isRetryable(err) {
            return err
        }

        lastErr = err

        // Calculate backoff with jitter
        delay := r.calculateDelay(attempt)

        select {
        case <-time.After(delay):
            continue
        case <-ctx.Done():
            return ctx.Err()
        }
    }

    return lastErr
}

func (r *RetryHandler) isRetryable(err error) bool {
    // Retry on network errors, 5xx responses, rate limiting
    var netErr net.Error
    if errors.As(err, &netErr) && netErr.Timeout() {
        return true
    }

    var httpErr *HTTPError
    if errors.As(err, &httpErr) {
        return httpErr.StatusCode >= 500 || httpErr.StatusCode == 429
    }

    return false
}

func (r *RetryHandler) calculateDelay(attempt int) time.Duration {
    // Exponential backoff with jitter
    delay := r.baseDelay * time.Duration(1<<attempt)
    if delay > r.maxDelay {
        delay = r.maxDelay
    }

    // Add jitter (±25%)
    jitter := time.Duration(rand.Float64()*0.5-0.25) * delay
    return delay + jitter
}
```

### Rate Limiter

```go
type RateLimiter struct {
    limiters map[string]*rate.Limiter
}

func NewRateLimiter(configs map[string]int) *RateLimiter {
    rl := &RateLimiter{
        limiters: make(map[string]*rate.Limiter),
    }

    for supplier, ratePerMin := range configs {
        // Convert per-minute to per-second
        rps := float64(ratePerMin) / 60.0
        rl.limiters[supplier] = rate.NewLimiter(rate.Limit(rps), ratePerMin/10)
    }

    return rl
}

func (rl *RateLimiter) Allow(supplier string) bool {
    limiter, ok := rl.limiters[supplier]
    if !ok {
        return true
    }
    return limiter.Allow()
}

func (rl *RateLimiter) Wait(ctx context.Context, supplier string) error {
    limiter, ok := rl.limiters[supplier]
    if !ok {
        return nil
    }
    return limiter.Wait(ctx)
}
```

**Rate Limits by Supplier:**

| Supplier | Rate Limit | Burst |
|----------|------------|-------|
| Amadeus | 1000/min | 100 |
| Sabre | 500/min | 50 |
| Travelport | 800/min | 80 |
| United NDC | 2000/min | 200 |
| Delta NDC | 2000/min | 200 |
| Southwest | 500/min | 50 |

---

## Response Normalization

All supplier responses are normalized to a unified schema:

```go
type NormalizedFlight struct {
    FlightID     string            `json:"flight_id"`
    SupplierCode string            `json:"supplier_code"`
    Segments     []FlightSegment   `json:"segments"`
    Pricing      FlightPricing     `json:"pricing"`
    Availability AvailabilityInfo  `json:"availability"`
    Baggage      BaggageInfo       `json:"baggage"`
    Amenities    []string          `json:"amenities"`
}

type FlightSegment struct {
    SegmentID       string    `json:"segment_id"`
    FlightNumber    string    `json:"flight_number"`
    CarrierCode     string    `json:"carrier_code"`
    CarrierName     string    `json:"carrier_name"`
    Origin          Airport   `json:"origin"`
    Destination     Airport   `json:"destination"`
    DepartureTime   time.Time `json:"departure_time"`
    ArrivalTime     time.Time `json:"arrival_time"`
    DurationMinutes int       `json:"duration_minutes"`
    AircraftCode    string    `json:"aircraft_code"`
    AircraftName    string    `json:"aircraft_name"`
    CabinClass      string    `json:"cabin_class"`
    FareClass       string    `json:"fare_class"`
}

type FlightPricing struct {
    BasePriceCents  int64  `json:"base_price_cents"`
    TaxesCents      int64  `json:"taxes_cents"`
    FeesCents       int64  `json:"fees_cents"`
    TotalCents      int64  `json:"total_cents"`
    Currency        string `json:"currency"`
    PricePerAdult   int64  `json:"price_per_adult_cents"`
    FareBreakdown   []FareBreakdown `json:"fare_breakdown"`
}
```

### Normalization Rules

| Field | Normalization Rule |
|-------|-------------------|
| Airport codes | Uppercase IATA codes |
| Times | UTC ISO 8601 format |
| Prices | Convert to cents, USD |
| Cabin class | economy, premium_economy, business, first |
| Duration | Calculate from departure/arrival if not provided |
| Carrier codes | Validate against airline reference data |

---

## Connection Management

### Connection Pooling

```go
type ConnectionPool struct {
    pools map[string]*http.Client
}

func NewConnectionPool(suppliers []SupplierConfig) *ConnectionPool {
    cp := &ConnectionPool{
        pools: make(map[string]*http.Client),
    }

    for _, supplier := range suppliers {
        cp.pools[supplier.Code] = &http.Client{
            Timeout: time.Duration(supplier.TimeoutMs) * time.Millisecond,
            Transport: &http.Transport{
                MaxIdleConns:        supplier.MaxConnections,
                MaxIdleConnsPerHost: supplier.MaxConnections,
                IdleConnTimeout:     90 * time.Second,
                TLSHandshakeTimeout: 10 * time.Second,
                DisableCompression:  false,
                DisableKeepAlives:   false,
            },
        }
    }

    return cp
}

func (cp *ConnectionPool) GetClient(supplier string) *http.Client {
    return cp.pools[supplier]
}
```

### Keep-Alive Strategy

- Enable HTTP/2 where supported
- Maintain persistent connections to GDS endpoints
- Connection warm-up on service startup
- Health checks to keep connections alive

---

## Metrics

```go
var (
    supplierRequests = prometheus.NewCounterVec(
        prometheus.CounterOpts{
            Name: "supplier_requests_total",
            Help: "Total requests to suppliers",
        },
        []string{"supplier", "operation", "status"},
    )

    supplierLatency = prometheus.NewHistogramVec(
        prometheus.HistogramOpts{
            Name:    "supplier_request_duration_seconds",
            Help:    "Supplier request latency",
            Buckets: []float64{0.1, 0.25, 0.5, 1, 2, 3, 5, 10},
        },
        []string{"supplier", "operation"},
    )

    circuitBreakerState = prometheus.NewGaugeVec(
        prometheus.GaugeOpts{
            Name: "circuit_breaker_state",
            Help: "Circuit breaker state (0=closed, 1=open, 2=half-open)",
        },
        []string{"supplier"},
    )

    rateLimitHits = prometheus.NewCounterVec(
        prometheus.CounterOpts{
            Name: "rate_limit_hits_total",
            Help: "Rate limit rejections",
        },
        []string{"supplier"},
    )
)
```

---

## Configuration

```yaml
supplier_gateway:
  # Global settings
  default_timeout_ms: 2000
  max_retry_attempts: 2
  retry_base_delay_ms: 100

  # Circuit breaker defaults
  circuit_breaker:
    failure_threshold: 5
    success_threshold: 3
    timeout_seconds: 30

  # Suppliers
  suppliers:
    amadeus:
      type: gds
      base_url: https://api.amadeus.com
      timeout_ms: 3000
      rate_limit_per_min: 1000
      max_connections: 100
      priority: 100

    sabre:
      type: gds
      base_url: https://api.sabre.com
      timeout_ms: 3000
      rate_limit_per_min: 500
      max_connections: 50
      priority: 90

    united:
      type: direct
      base_url: https://api.united.com
      timeout_ms: 2000
      rate_limit_per_min: 2000
      max_connections: 100
      priority: 95

    delta:
      type: direct
      base_url: https://api.delta.com
      timeout_ms: 2000
      rate_limit_per_min: 2000
      max_connections: 100
      priority: 95

    spirit:
      type: lcc
      base_url: https://api.spirit.com
      timeout_ms: 4000
      rate_limit_per_min: 200
      max_connections: 20
      priority: 70
```

---

## Monitoring & Alerting

### Key Alerts

| Metric | Threshold | Severity |
|--------|-----------|----------|
| Supplier error rate | > 10% | Warning |
| Supplier error rate | > 25% | Critical |
| Circuit breaker open | Any | Warning |
| P99 latency | > 5s | Warning |
| Rate limit rejections | > 100/min | Warning |

### Dashboard Panels

1. Supplier availability (success rate by supplier)
2. Latency percentiles per supplier
3. Circuit breaker states
4. Rate limit utilization
5. Error breakdown by type
6. Request volume per supplier
