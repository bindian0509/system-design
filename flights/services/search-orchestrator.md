# Search Orchestrator Service

## Overview

The Search Orchestrator is the core service responsible for handling flight search requests. It coordinates parallel queries to multiple suppliers, aggregates results, applies pricing, and streams progressive results to clients.

---

## Responsibilities

1. **Request Validation:** Validate and normalize search parameters
2. **Cache Management:** Check and populate search result cache
3. **Supplier Fan-Out:** Dispatch parallel requests to applicable suppliers
4. **Result Aggregation:** Combine, deduplicate, and rank results
5. **Dynamic Pricing:** Apply markup and demand-based pricing
6. **Progressive Streaming:** Return results incrementally via SSE
7. **Analytics:** Publish search events for ML and analytics

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Search Orchestrator Service                         │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                        Request Handler                                │   │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐     │   │
│  │  │ Validator  │  │ Normalizer │  │Rate Limiter│  │   Router   │     │   │
│  │  └────────────┘  └────────────┘  └────────────┘  └────────────┘     │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                        Cache Layer                                    │   │
│  │  ┌────────────────────┐     ┌────────────────────────────────────┐  │   │
│  │  │    Local Cache     │────>│          Redis Cluster             │  │   │
│  │  │   (60s TTL, LRU)   │     │        (2-30 min TTL)              │  │   │
│  │  └────────────────────┘     └────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                              Cache Miss                                      │
│                                    ▼                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                      Supplier Dispatcher                              │   │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────────────┐ │   │
│  │  │ Route Analyzer │  │Supplier Selector│  │  Parallel Executor    │ │   │
│  │  │(which suppliers│  │(health, priority│  │  (fan-out, timeout)   │ │   │
│  │  │ serve route)   │  │ rate limits)   │  │                        │ │   │
│  │  └────────────────┘  └────────────────┘  └────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                      Result Processor                                 │   │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐     │   │
│  │  │Aggregator  │  │Deduplicator│  │  Pricer    │  │   Ranker   │     │   │
│  │  └────────────┘  └────────────┘  └────────────┘  └────────────┘     │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                      Response Streamer                                │   │
│  │  ┌────────────────────────────────────────────────────────────────┐ │   │
│  │  │              Server-Sent Events (SSE) Handler                   │ │   │
│  │  │     Progressive batches at 500ms, 1s, 2s, final at 3s         │ │   │
│  │  └────────────────────────────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Search Flow

### Step 1: Request Validation

```go
type SearchRequest struct {
    Origin          string    `json:"origin" validate:"required,len=3,alpha"`
    Destination     string    `json:"destination" validate:"required,len=3,alpha"`
    DepartureDate   string    `json:"departure_date" validate:"required,date"`
    ReturnDate      string    `json:"return_date,omitempty" validate:"omitempty,date,gtfield=DepartureDate"`
    Adults          int       `json:"adults" validate:"required,min=1,max=9"`
    Children        int       `json:"children" validate:"min=0,max=8"`
    Infants         int       `json:"infants" validate:"min=0,max=4"`
    CabinClass      string    `json:"cabin_class" validate:"oneof=economy premium_economy business first"`
    DirectOnly      bool      `json:"direct_only"`
    MaxStops        int       `json:"max_stops" validate:"min=0,max=3"`
}

func (s *SearchService) Validate(req *SearchRequest) error {
    // Structural validation
    if err := validator.Struct(req); err != nil {
        return ValidationError{Errors: err}
    }

    // Business validation
    if req.Origin == req.Destination {
        return ValidationError{Field: "destination", Message: "must differ from origin"}
    }

    departureDate, _ := time.Parse("2006-01-02", req.DepartureDate)
    if departureDate.Before(time.Now().Truncate(24 * time.Hour)) {
        return ValidationError{Field: "departure_date", Message: "cannot be in the past"}
    }

    if departureDate.After(time.Now().AddDate(1, 0, 0)) {
        return ValidationError{Field: "departure_date", Message: "cannot be more than 1 year ahead"}
    }

    // Verify airports exist
    if !s.airportRepo.Exists(req.Origin) {
        return ValidationError{Field: "origin", Message: "invalid airport code"}
    }

    return nil
}
```

### Step 2: Cache Check

```go
func (s *SearchService) Search(ctx context.Context, req *SearchRequest) (*SearchResponse, error) {
    cacheKey := s.generateCacheKey(req)

    // Check local cache first (L2)
    if cached, ok := s.localCache.Get(cacheKey); ok {
        metrics.CacheHits.WithLabelValues("local").Inc()
        return cached.(*SearchResponse), nil
    }

    // Check Redis (L3)
    cached, err := s.redis.Get(ctx, cacheKey)
    if err == nil && cached != "" {
        metrics.CacheHits.WithLabelValues("redis").Inc()
        response := deserializeResponse(cached)
        s.localCache.Set(cacheKey, response, 60*time.Second)
        return response, nil
    }

    metrics.CacheMisses.Inc()

    // Cache miss - execute search
    return s.executeSearch(ctx, req, cacheKey)
}
```

### Step 3: Supplier Selection

Determine which suppliers can serve this route:

```go
type SupplierSelector struct {
    supplierRepo    SupplierRepository
    circuitBreaker  CircuitBreakerManager
    routeCoverage   RouteCoverageIndex
}

func (ss *SupplierSelector) SelectSuppliers(route Route) []Supplier {
    // Get all suppliers that cover this route
    candidates := ss.routeCoverage.GetSuppliers(route.Origin, route.Destination)

    var selected []Supplier
    for _, supplier := range candidates {
        // Skip if circuit breaker is open
        if ss.circuitBreaker.IsOpen(supplier.Code) {
            continue
        }

        // Skip if supplier is over rate limit
        if !ss.canMakeRequest(supplier.Code) {
            continue
        }

        selected = append(selected, supplier)
    }

    // Sort by priority (quality, speed, commission)
    sort.Slice(selected, func(i, j int) bool {
        return selected[i].Priority > selected[j].Priority
    })

    // Cap at 20 suppliers to avoid excessive fan-out
    if len(selected) > 20 {
        selected = selected[:20]
    }

    return selected
}
```

### Step 4: Parallel Execution

```go
func (s *SearchService) executeSearch(ctx context.Context, req *SearchRequest, cacheKey string) (*SearchResponse, error) {
    route := Route{Origin: req.Origin, Destination: req.Destination}
    suppliers := s.supplierSelector.SelectSuppliers(route)

    // Create result channels
    resultsCh := make(chan SupplierResult, len(suppliers))
    errorsCh := make(chan SupplierError, len(suppliers))

    // Set overall timeout
    searchCtx, cancel := context.WithTimeout(ctx, 3*time.Second)
    defer cancel()

    // Fan out to all suppliers
    var wg sync.WaitGroup
    for _, supplier := range suppliers {
        wg.Add(1)
        go func(sup Supplier) {
            defer wg.Done()

            // Per-supplier timeout
            supCtx, supCancel := context.WithTimeout(searchCtx, time.Duration(sup.TimeoutMs)*time.Millisecond)
            defer supCancel()

            startTime := time.Now()
            results, err := s.supplierGateway.Search(supCtx, sup.Code, req)
            latency := time.Since(startTime)

            if err != nil {
                errorsCh <- SupplierError{Supplier: sup.Code, Error: err}
                s.circuitBreaker.RecordFailure(sup.Code)
                metrics.SupplierErrors.WithLabelValues(sup.Code).Inc()
            } else {
                resultsCh <- SupplierResult{
                    Supplier: sup.Code,
                    Flights:  results,
                    Latency:  latency,
                }
                s.circuitBreaker.RecordSuccess(sup.Code)
                metrics.SupplierLatency.WithLabelValues(sup.Code).Observe(latency.Seconds())
            }
        }(supplier)
    }

    // Close channels when all goroutines complete
    go func() {
        wg.Wait()
        close(resultsCh)
        close(errorsCh)
    }()

    // Aggregate results
    return s.aggregateResults(searchCtx, resultsCh, errorsCh, req, cacheKey)
}
```

### Step 5: Result Aggregation

```go
type ResultAggregator struct {
    pricingEngine  *PricingEngine
    deduplicator   *FlightDeduplicator
}

func (s *SearchService) aggregateResults(
    ctx context.Context,
    resultsCh <-chan SupplierResult,
    errorsCh <-chan SupplierError,
    req *SearchRequest,
    cacheKey string,
) (*SearchResponse, error) {
    var allFlights []Flight
    var supplierErrors []SupplierError
    suppliersQueried := make([]string, 0)

    // Collect all results
    for {
        select {
        case result, ok := <-resultsCh:
            if !ok {
                goto aggregate
            }
            allFlights = append(allFlights, result.Flights...)
            suppliersQueried = append(suppliersQueried, result.Supplier)

        case err, ok := <-errorsCh:
            if !ok {
                continue
            }
            supplierErrors = append(supplierErrors, err)

        case <-ctx.Done():
            goto aggregate
        }
    }

aggregate:
    // Deduplicate flights (same flight number, times, but from different suppliers)
    uniqueFlights := s.deduplicator.Deduplicate(allFlights)

    // Apply dynamic pricing
    pricedFlights := s.pricingEngine.ApplyPricing(uniqueFlights, req)

    // Sort by requested criteria
    sortedFlights := s.sortFlights(pricedFlights, req.SortBy)

    response := &SearchResponse{
        SearchID:         generateSearchID(),
        Origin:           req.Origin,
        Destination:      req.Destination,
        DepartureDate:    req.DepartureDate,
        Results:          sortedFlights,
        TotalResults:     len(sortedFlights),
        SuppliersQueried: suppliersQueried,
        Errors:           supplierErrors,
    }

    // Cache results asynchronously
    go s.cacheResults(cacheKey, response, req.DepartureDate)

    // Publish analytics event asynchronously
    go s.publishSearchEvent(req, response)

    return response, nil
}
```

### Step 6: Deduplication

Flights from different suppliers may represent the same flight:

```go
type FlightDeduplicator struct{}

func (d *FlightDeduplicator) Deduplicate(flights []Flight) []Flight {
    // Group by flight fingerprint
    groups := make(map[string][]Flight)

    for _, flight := range flights {
        fingerprint := d.generateFingerprint(flight)
        groups[fingerprint] = append(groups[fingerprint], flight)
    }

    // For each group, select the best offer
    result := make([]Flight, 0, len(groups))
    for _, group := range groups {
        best := d.selectBestOffer(group)
        result = append(result, best)
    }

    return result
}

func (d *FlightDeduplicator) generateFingerprint(flight Flight) string {
    // Create fingerprint from flight-defining characteristics
    var segments []string
    for _, seg := range flight.Segments {
        segments = append(segments, fmt.Sprintf(
            "%s-%s-%s-%s",
            seg.FlightNumber,
            seg.DepartureTime.Format("200601021504"),
            seg.Origin,
            seg.Destination,
        ))
    }
    return strings.Join(segments, "|")
}

func (d *FlightDeduplicator) selectBestOffer(offers []Flight) Flight {
    // Sort by price, then by supplier priority
    sort.Slice(offers, func(i, j int) bool {
        if offers[i].Pricing.TotalCents != offers[j].Pricing.TotalCents {
            return offers[i].Pricing.TotalCents < offers[j].Pricing.TotalCents
        }
        return offers[i].SupplierPriority > offers[j].SupplierPriority
    })
    return offers[0]
}
```

---

## Progressive Results (SSE)

For better user experience, return results progressively:

```go
func (s *SearchService) SearchStream(ctx context.Context, req *SearchRequest, w http.ResponseWriter) error {
    // Set SSE headers
    w.Header().Set("Content-Type", "text/event-stream")
    w.Header().Set("Cache-Control", "no-cache")
    w.Header().Set("Connection", "keep-alive")

    flusher, ok := w.(http.Flusher)
    if !ok {
        return errors.New("streaming not supported")
    }

    // Create batching channels
    batchCh := make(chan []Flight, 10)
    doneCh := make(chan struct{})

    // Start search in background
    go func() {
        defer close(batchCh)
        s.executeStreamingSearch(ctx, req, batchCh)
    }()

    // Milestones for sending batches
    milestones := []time.Duration{500 * time.Millisecond, 1 * time.Second, 2 * time.Second}
    milestoneIdx := 0
    startTime := time.Now()
    var accumulatedFlights []Flight
    batchNumber := 0

    ticker := time.NewTicker(100 * time.Millisecond)
    defer ticker.Stop()

    for {
        select {
        case flights, ok := <-batchCh:
            if !ok {
                // Send final batch
                if len(accumulatedFlights) > 0 {
                    s.sendBatch(w, flusher, accumulatedFlights, batchNumber, true)
                }
                s.sendComplete(w, flusher)
                return nil
            }
            accumulatedFlights = append(accumulatedFlights, flights...)

        case <-ticker.C:
            elapsed := time.Since(startTime)
            if milestoneIdx < len(milestones) && elapsed >= milestones[milestoneIdx] {
                if len(accumulatedFlights) > 0 {
                    batchNumber++
                    s.sendBatch(w, flusher, accumulatedFlights, batchNumber, false)
                    accumulatedFlights = nil
                }
                milestoneIdx++
            }

        case <-ctx.Done():
            return ctx.Err()
        }
    }
}

func (s *SearchService) sendBatch(w http.ResponseWriter, flusher http.Flusher, flights []Flight, batchNum int, isFinal bool) {
    batch := BatchEvent{
        BatchNumber: batchNum,
        Results:     flights,
        IsFinal:     isFinal,
    }
    data, _ := json.Marshal(batch)
    fmt.Fprintf(w, "event: batch\ndata: %s\n\n", data)
    flusher.Flush()
}

func (s *SearchService) sendComplete(w http.ResponseWriter, flusher http.Flusher) {
    fmt.Fprintf(w, "event: complete\ndata: {\"status\":\"done\"}\n\n")
    flusher.Flush()
}
```

---

## Configuration

```yaml
search_service:
  # Timeouts
  overall_timeout_ms: 3000
  default_supplier_timeout_ms: 2000
  cache_check_timeout_ms: 100

  # Fan-out limits
  max_suppliers_per_search: 20
  parallel_workers: 50

  # Result limits
  max_results_per_search: 500
  max_results_per_supplier: 100

  # Progressive streaming
  sse_enabled: true
  sse_milestones_ms: [500, 1000, 2000]

  # Circuit breaker
  circuit_breaker:
    failure_threshold: 5
    success_threshold: 3
    timeout_seconds: 30

  # Caching
  cache:
    local_enabled: true
    local_max_entries: 10000
    local_ttl_seconds: 60
    redis_enabled: true

  # Scaling
  instances:
    min: 20
    max: 100
    target_cpu_percent: 70
```

---

## Error Handling

### Partial Failures

If some suppliers fail, return results from successful ones:

```go
func (s *SearchService) handlePartialFailure(
    results []Flight,
    errors []SupplierError,
) *SearchResponse {
    response := &SearchResponse{
        Results: results,
        Metadata: SearchMetadata{
            PartialResults: len(errors) > 0,
            FailedSuppliers: extractSupplierCodes(errors),
        },
    }

    // Log failures for monitoring
    for _, err := range errors {
        log.Warn("Supplier search failed",
            "supplier", err.Supplier,
            "error", err.Error,
        )
    }

    return response
}
```

### Complete Failure

If all suppliers fail, return appropriate error:

```go
func (s *SearchService) handleCompleteFailure(errors []SupplierError) error {
    // Check if it's a rate limiting issue
    if allRateLimited(errors) {
        return TooManyRequestsError{
            Message: "Search temporarily unavailable, please try again",
            RetryAfter: 30,
        }
    }

    // Check if it's a timeout issue
    if allTimeouts(errors) {
        return GatewayTimeoutError{
            Message: "Search timed out, please try again",
        }
    }

    // Generic supplier error
    return ServiceUnavailableError{
        Message: "Unable to complete search at this time",
    }
}
```

---

## Metrics

```go
var (
    searchRequests = prometheus.NewCounterVec(
        prometheus.CounterOpts{
            Name: "search_requests_total",
            Help: "Total number of search requests",
        },
        []string{"status", "cache_hit"},
    )

    searchLatency = prometheus.NewHistogramVec(
        prometheus.HistogramOpts{
            Name:    "search_latency_seconds",
            Help:    "Search request latency",
            Buckets: []float64{0.1, 0.25, 0.5, 1, 2, 3, 5},
        },
        []string{"cache_hit"},
    )

    resultsCount = prometheus.NewHistogram(
        prometheus.HistogramOpts{
            Name:    "search_results_count",
            Help:    "Number of results per search",
            Buckets: []float64{0, 10, 25, 50, 100, 200, 500},
        },
    )

    supplierLatency = prometheus.NewHistogramVec(
        prometheus.HistogramOpts{
            Name:    "supplier_search_latency_seconds",
            Help:    "Per-supplier search latency",
            Buckets: []float64{0.1, 0.25, 0.5, 1, 2, 3, 5},
        },
        []string{"supplier"},
    )

    supplierErrors = prometheus.NewCounterVec(
        prometheus.CounterOpts{
            Name: "supplier_search_errors_total",
            Help: "Supplier search errors",
        },
        []string{"supplier", "error_type"},
    )
)
```

---

## Scaling

### Horizontal Scaling

| Load | Instances | vCPU | Memory |
|------|-----------|------|--------|
| Normal (1,200 RPS) | 20 | 4 | 8GB |
| Peak (5,000 RPS) | 80 | 4 | 8GB |
| Burst (10,000 RPS) | 150 | 4 | 8GB |

### Auto-Scaling Policy

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: search-service-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: search-service
  minReplicas: 20
  maxReplicas: 150
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Pods
      pods:
        metric:
          name: http_requests_per_second
        target:
          type: AverageValue
          averageValue: "100"
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 30
      policies:
        - type: Percent
          value: 100
          periodSeconds: 15
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Percent
          value: 10
          periodSeconds: 60
```
