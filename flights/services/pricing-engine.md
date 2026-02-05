# Pricing Engine Service

## Overview

The Pricing Engine applies dynamic pricing to flight search results, calculating final prices based on supplier base prices, demand signals, booking window, seasonality, and business rules. The goal is to maximize revenue while maintaining competitive pricing and user trust.

---

## Pricing Formula

```
Final Price = Base Price × Booking Window Factor × Demand Factor × Seasonality Factor × Margin Factor
```

### Factor Bounds

| Factor | Min | Max | Description |
|--------|-----|-----|-------------|
| Booking Window | 0.95 | 1.35 | Based on days until departure |
| Demand | 0.90 | 1.15 | ML-derived from search velocity |
| Seasonality | 0.85 | 1.45 | Holidays, peak travel periods |
| Margin | 1.03 | 1.08 | Commission-based, per supplier |

**Total Adjustment Range:** -18% to +84%

To maintain user trust and avoid perception of price manipulation, the combined adjustment is bounded:
- **Maximum increase:** +25%
- **Maximum decrease:** -15%

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Pricing Engine Service                             │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                        Price Calculator                               │   │
│  │                                                                        │   │
│  │  Input: Base Price + Context (route, date, user, time)                │   │
│  │  Output: Final Price + Breakdown                                       │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│          ┌─────────────────────────┼─────────────────────────┐              │
│          ▼                         ▼                         ▼              │
│  ┌──────────────┐         ┌──────────────┐         ┌──────────────┐        │
│  │   Booking    │         │    Demand    │         │ Seasonality  │        │
│  │   Window     │         │   Factor     │         │   Factor     │        │
│  │  Calculator  │         │  Calculator  │         │  Calculator  │        │
│  └──────────────┘         └──────────────┘         └──────────────┘        │
│          │                         │                         │              │
│          │                         ▼                         │              │
│          │                ┌──────────────┐                   │              │
│          │                │  ML Model    │                   │              │
│          │                │  (Demand     │                   │              │
│          │                │  Prediction) │                   │              │
│          │                └──────────────┘                   │              │
│          │                         │                         │              │
│          └─────────────────────────┼─────────────────────────┘              │
│                                    ▼                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                       Margin Calculator                               │   │
│  │                  (Per-supplier commission rules)                       │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                       Bound Enforcer                                  │   │
│  │                    (Cap total adjustment)                             │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                      Price Formatter                                  │   │
│  │          (Round, format, generate breakdown)                          │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Factor Calculations

### 1. Booking Window Factor

Prices typically increase as departure approaches due to reduced inventory and higher urgency.

```go
func (p *PricingEngine) CalculateBookingWindowFactor(departureDate time.Time) float64 {
    daysUntilDeparture := int(time.Until(departureDate).Hours() / 24)

    // Piecewise linear function
    switch {
    case daysUntilDeparture > 60:
        // Early booking discount
        return 0.95
    case daysUntilDeparture > 30:
        // Standard pricing
        return 1.00
    case daysUntilDeparture > 14:
        // Slight premium
        return 1.05
    case daysUntilDeparture > 7:
        // Increased demand
        return 1.12
    case daysUntilDeparture > 3:
        // High urgency
        return 1.22
    case daysUntilDeparture > 1:
        // Last minute
        return 1.30
    default:
        // Same day / next day
        return 1.35
    }
}
```

**Booking Window Factor Curve:**

```
Factor
  1.35 |                                         ____
  1.30 |                                    ____/
  1.22 |                               ____/
  1.12 |                          ____/
  1.05 |                     ____/
  1.00 |           _________/
  0.95 |__________/
       +----+----+----+----+----+----+----+----+----+
           60   45   30   21   14    7    3    1   Days
```

### 2. Demand Factor (ML-Driven)

The demand factor is derived from real-time signals indicating market demand.

**Input Features:**
| Feature | Description | Weight |
|---------|-------------|--------|
| Search velocity | Searches per hour for this route | 0.25 |
| Search trend | 7-day vs 30-day average | 0.15 |
| Seat availability | Remaining seats across suppliers | 0.20 |
| Historical conversion | Booking rate for similar searches | 0.15 |
| Competitor pricing | Price relative to market | 0.10 |
| Time of day | Peak vs off-peak search times | 0.10 |
| User segment | New vs returning, loyalty tier | 0.05 |

```go
type DemandFactorCalculator struct {
    mlClient      MLServiceClient
    metricsCache  *DemandMetricsCache
}

func (d *DemandFactorCalculator) Calculate(ctx context.Context, route Route, date time.Time) (float64, error) {
    // Fetch real-time demand metrics
    metrics, err := d.metricsCache.Get(route, date)
    if err != nil {
        // Fallback to neutral factor
        return 1.0, nil
    }

    // Call ML model for demand prediction
    prediction, err := d.mlClient.PredictDemand(ctx, DemandRequest{
        Route:            route,
        DepartureDate:    date,
        SearchVelocity:   metrics.SearchesPerHour,
        SeatsRemaining:   metrics.AvgSeatsRemaining,
        HistoricalConversion: metrics.ConversionRate,
        CurrentHour:      time.Now().Hour(),
    })
    if err != nil {
        // Fallback to rule-based calculation
        return d.calculateRuleBased(metrics)
    }

    // Bound the factor
    factor := prediction.DemandFactor
    if factor < 0.90 {
        factor = 0.90
    }
    if factor > 1.15 {
        factor = 1.15
    }

    return factor, nil
}

func (d *DemandFactorCalculator) calculateRuleBased(metrics DemandMetrics) float64 {
    // Simple rule-based fallback
    factor := 1.0

    // High search velocity → increase
    if metrics.SearchesPerHour > 100 {
        factor += 0.05
    }
    if metrics.SearchesPerHour > 500 {
        factor += 0.05
    }

    // Low seat availability → increase
    if metrics.AvgSeatsRemaining < 10 {
        factor += 0.05
    }
    if metrics.AvgSeatsRemaining < 5 {
        factor += 0.05
    }

    // High conversion rate → increase
    if metrics.ConversionRate > 0.05 {
        factor += 0.03
    }

    return math.Min(factor, 1.15)
}
```

### 3. Seasonality Factor

Based on historical patterns, holidays, and events.

```go
type SeasonalityCalculator struct {
    holidayCalendar *HolidayCalendar
    eventDatabase   *EventDatabase
    baselineData    *SeasonalityBaseline
}

func (s *SeasonalityCalculator) Calculate(route Route, date time.Time) float64 {
    factor := 1.0

    // Check holidays (origin and destination)
    if holiday := s.holidayCalendar.GetHoliday(route.Origin, date); holiday != nil {
        factor *= holiday.PriceFactor
    }
    if holiday := s.holidayCalendar.GetHoliday(route.Destination, date); holiday != nil {
        factor *= holiday.PriceFactor
    }

    // Check major events
    if event := s.eventDatabase.GetEvent(route.Destination, date, 3); event != nil {
        factor *= event.PriceFactor
    }

    // Apply baseline seasonality
    baseline := s.baselineData.GetFactor(route, date.Month(), date.Weekday())
    factor *= baseline

    // Bound the factor
    if factor < 0.85 {
        factor = 0.85
    }
    if factor > 1.45 {
        factor = 1.45
    }

    return factor
}
```

**Seasonality Calendar Examples:**

| Period | Factor | Description |
|--------|--------|-------------|
| Christmas (Dec 20-26) | 1.40 | Peak holiday travel |
| Thanksgiving (US) | 1.35 | Peak US domestic |
| Spring Break | 1.25 | US vacation period |
| Summer (Jun-Aug) | 1.15 | General high season |
| January (post-holiday) | 0.85 | Low season |
| September (post-summer) | 0.90 | Shoulder season |

### 4. Margin Factor

Based on supplier agreements and business requirements.

```go
type MarginCalculator struct {
    supplierContracts map[string]SupplierContract
}

type SupplierContract struct {
    Code            string
    CommissionRate  float64  // Our commission (e.g., 0.05 = 5%)
    MinMargin       float64  // Minimum margin to apply
    MaxMargin       float64  // Maximum margin to apply
    VolumeDiscounts []VolumeDiscount
}

func (m *MarginCalculator) Calculate(supplierCode string, basePriceCents int64) float64 {
    contract, ok := m.supplierContracts[supplierCode]
    if !ok {
        // Default margin
        return 1.05
    }

    // Start with minimum margin
    margin := contract.MinMargin

    // Adjust based on price tier
    if basePriceCents > 100000 { // > $1000
        margin = contract.MaxMargin
    } else if basePriceCents > 50000 { // > $500
        margin = (contract.MinMargin + contract.MaxMargin) / 2
    }

    return margin
}
```

**Typical Margin Rates:**

| Supplier Type | Min Margin | Max Margin |
|---------------|------------|------------|
| GDS | 1.03 | 1.06 |
| Direct Airlines | 1.04 | 1.07 |
| LCC | 1.05 | 1.08 |
| Aggregators | 1.04 | 1.06 |

---

## Price Calculation Flow

```go
type PricingEngine struct {
    bookingWindowCalc  *BookingWindowCalculator
    demandFactorCalc   *DemandFactorCalculator
    seasonalityCalc    *SeasonalityCalculator
    marginCalc         *MarginCalculator
    config             PricingConfig
}

type PricingContext struct {
    Route         Route
    DepartureDate time.Time
    SupplierCode  string
    BasePriceUSD  float64
}

type PricedResult struct {
    FinalPriceCents int64
    BasePriceCents  int64
    Breakdown       PriceBreakdown
}

type PriceBreakdown struct {
    BasePriceCents      int64   `json:"base_price_cents"`
    BookingWindowFactor float64 `json:"booking_window_factor"`
    DemandFactor        float64 `json:"demand_factor"`
    SeasonalityFactor   float64 `json:"seasonality_factor"`
    MarginFactor        float64 `json:"margin_factor"`
    TotalMultiplier     float64 `json:"total_multiplier"`
    FinalPriceCents     int64   `json:"final_price_cents"`
}

func (p *PricingEngine) CalculatePrice(ctx context.Context, input PricingContext) (*PricedResult, error) {
    // Calculate individual factors
    bookingFactor := p.bookingWindowCalc.Calculate(input.DepartureDate)
    demandFactor, _ := p.demandFactorCalc.Calculate(ctx, input.Route, input.DepartureDate)
    seasonFactor := p.seasonalityCalc.Calculate(input.Route, input.DepartureDate)
    marginFactor := p.marginCalc.Calculate(input.SupplierCode, int64(input.BasePriceUSD*100))

    // Calculate raw multiplier
    rawMultiplier := bookingFactor * demandFactor * seasonFactor * marginFactor

    // Apply bounds to total adjustment
    boundedMultiplier := p.applyBounds(rawMultiplier)

    // Calculate final price
    baseCents := int64(input.BasePriceUSD * 100)
    finalCents := int64(float64(baseCents) * boundedMultiplier)

    // Round to nearest dollar
    finalCents = roundToNearestDollar(finalCents)

    return &PricedResult{
        FinalPriceCents: finalCents,
        BasePriceCents:  baseCents,
        Breakdown: PriceBreakdown{
            BasePriceCents:      baseCents,
            BookingWindowFactor: bookingFactor,
            DemandFactor:        demandFactor,
            SeasonalityFactor:   seasonFactor,
            MarginFactor:        marginFactor,
            TotalMultiplier:     boundedMultiplier,
            FinalPriceCents:     finalCents,
        },
    }, nil
}

func (p *PricingEngine) applyBounds(multiplier float64) float64 {
    // Maximum 25% increase
    if multiplier > 1.25 {
        return 1.25
    }
    // Maximum 15% decrease
    if multiplier < 0.85 {
        return 0.85
    }
    return multiplier
}

func roundToNearestDollar(cents int64) int64 {
    // Round to nearest 100 cents (dollar)
    return ((cents + 50) / 100) * 100
}
```

---

## Batch Pricing

For efficiency, price multiple flights at once:

```go
func (p *PricingEngine) PriceBatch(ctx context.Context, flights []Flight, route Route, departureDate time.Time) []PricedFlight {
    // Pre-compute shared factors
    bookingFactor := p.bookingWindowCalc.Calculate(departureDate)
    demandFactor, _ := p.demandFactorCalc.Calculate(ctx, route, departureDate)
    seasonFactor := p.seasonalityCalc.Calculate(route, departureDate)

    results := make([]PricedFlight, len(flights))

    for i, flight := range flights {
        marginFactor := p.marginCalc.Calculate(flight.SupplierCode, flight.BasePriceCents)

        rawMultiplier := bookingFactor * demandFactor * seasonFactor * marginFactor
        boundedMultiplier := p.applyBounds(rawMultiplier)

        finalCents := int64(float64(flight.BasePriceCents) * boundedMultiplier)
        finalCents = roundToNearestDollar(finalCents)

        results[i] = PricedFlight{
            Flight:          flight,
            FinalPriceCents: finalCents,
            Breakdown: PriceBreakdown{
                BasePriceCents:      flight.BasePriceCents,
                BookingWindowFactor: bookingFactor,
                DemandFactor:        demandFactor,
                SeasonalityFactor:   seasonFactor,
                MarginFactor:        marginFactor,
                TotalMultiplier:     boundedMultiplier,
                FinalPriceCents:     finalCents,
            },
        }
    }

    return results
}
```

---

## A/B Testing

The pricing engine supports A/B testing of pricing strategies:

```go
type PricingExperiment struct {
    ID          string
    Name        string
    Variant     string
    TrafficPct  int
    Config      PricingConfig
    StartDate   time.Time
    EndDate     time.Time
}

func (p *PricingEngine) GetPricingConfig(userID string) PricingConfig {
    // Check active experiments
    for _, exp := range p.activeExperiments {
        if p.isUserInExperiment(userID, exp) {
            return exp.Config
        }
    }
    return p.defaultConfig
}

func (p *PricingEngine) isUserInExperiment(userID string, exp PricingExperiment) bool {
    // Deterministic assignment based on user ID
    hash := fnv.New32a()
    hash.Write([]byte(userID + exp.ID))
    bucket := hash.Sum32() % 100
    return int(bucket) < exp.TrafficPct
}
```

**Experiment Metrics:**
- Conversion rate (searches to bookings)
- Revenue per search
- Average ticket price
- User satisfaction (NPS)

---

## Fairness & Transparency

### Anti-Discrimination Rules

```go
func (p *PricingEngine) ValidateNonDiscrimination(ctx context.Context, prices []PricedFlight) error {
    // Ensure pricing is consistent across user demographics
    // No pricing based on:
    // - Device type (mobile vs desktop)
    // - Browser/OS
    // - Geographic location of user (only route matters)
    // - User's search history (retargeting)
    // - User's perceived price sensitivity

    return nil
}
```

### Price Transparency

Include breakdown in API responses:

```json
{
  "final_price_cents": 34900,
  "price_breakdown": {
    "base_price_cents": 29900,
    "taxes_cents": 4500,
    "our_service_fee_cents": 500,
    "total_cents": 34900
  },
  "price_factors": {
    "booking_window": "Standard pricing",
    "demand": "Normal demand",
    "season": "Summer travel season (+5%)"
  }
}
```

---

## Caching

Price factors are cached to reduce computation:

```go
type PricingCache struct {
    redis *redis.Client
}

func (c *PricingCache) GetDemandFactor(route Route, date time.Time) (float64, bool) {
    key := fmt.Sprintf("demand_factor:%s-%s:%s", route.Origin, route.Destination, date.Format("2006-01-02"))
    val, err := c.redis.Get(ctx, key).Float64()
    if err != nil {
        return 0, false
    }
    return val, true
}

func (c *PricingCache) SetDemandFactor(route Route, date time.Time, factor float64) {
    key := fmt.Sprintf("demand_factor:%s-%s:%s", route.Origin, route.Destination, date.Format("2006-01-02"))
    c.redis.Set(ctx, key, factor, 5*time.Minute)
}
```

**Cache TTLs:**

| Factor | TTL | Reason |
|--------|-----|--------|
| Booking Window | No cache | Deterministic calculation |
| Demand Factor | 5 minutes | Changes based on real-time signals |
| Seasonality | 24 hours | Static calendar-based |
| Margin | 1 hour | Contract changes are rare |

---

## Metrics

```go
var (
    pricingRequests = prometheus.NewCounterVec(
        prometheus.CounterOpts{
            Name: "pricing_requests_total",
            Help: "Total pricing calculations",
        },
        []string{"route_type"},
    )

    priceMultiplier = prometheus.NewHistogramVec(
        prometheus.HistogramOpts{
            Name:    "price_multiplier",
            Help:    "Distribution of final price multipliers",
            Buckets: []float64{0.85, 0.90, 0.95, 1.0, 1.05, 1.10, 1.15, 1.20, 1.25},
        },
        []string{"factor_type"},
    )

    pricingLatency = prometheus.NewHistogram(
        prometheus.HistogramOpts{
            Name:    "pricing_calculation_duration_seconds",
            Help:    "Time to calculate prices",
            Buckets: []float64{0.001, 0.005, 0.01, 0.025, 0.05, 0.1},
        },
    )

    revenueImpact = prometheus.NewCounterVec(
        prometheus.CounterOpts{
            Name: "pricing_revenue_impact_cents",
            Help: "Revenue impact from dynamic pricing",
        },
        []string{"direction"}, // increase, decrease
    )
)
```

---

## Configuration

```yaml
pricing_engine:
  # Booking window factors
  booking_window:
    early_booking_discount: 0.95  # > 60 days
    standard: 1.00               # 30-60 days
    slight_premium: 1.05         # 14-30 days
    increased_demand: 1.12       # 7-14 days
    high_urgency: 1.22          # 3-7 days
    last_minute: 1.30           # 1-3 days
    same_day: 1.35              # < 1 day

  # Demand factor bounds
  demand:
    min_factor: 0.90
    max_factor: 1.15
    ml_model_endpoint: "http://ml-service:8080/predict/demand"
    fallback_to_rules: true

  # Total adjustment bounds
  bounds:
    max_increase: 0.25   # +25%
    max_decrease: 0.15   # -15%

  # Caching
  cache:
    demand_factor_ttl_seconds: 300
    seasonality_ttl_seconds: 86400

  # A/B testing
  experiments:
    enabled: true
    max_concurrent: 3
```
