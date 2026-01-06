# Why Separate ORDER_PAYOUT_MAPPING Table?

**Question**: Why create a separate `ORDER_PAYOUT_MAPPING` table when we could add payout fields directly to the existing Order table in OrderService?

---

## Short Answer

Two primary reasons:
1. **One order can have multiple sellers** → Need N rows per order (one per seller)
2. **Microservice boundaries** → Payment System shouldn't write to OrderService's database

---

## Detailed Reasoning

### 1. Multi-Seller Orders

A single order can contain products from multiple sellers:

```
Order ORD-123:
  - Product A from Seller S001: $45.00
  - Product B from Seller S002: $30.00
  - Product C from Seller S001: $25.00
```

This requires **2 mapping records**:

| order_id | seller_id | seller_amount |
|----------|-----------|---------------|
| ORD-123  | S001      | $70.00        |
| ORD-123  | S002      | $30.00        |

The Order table has **1 row per order**, but payouts need **N rows** (one per seller per order).

### 2. Microservice Boundaries

```
┌─────────────────────┐      Events      ┌─────────────────────────┐
│   OrderService      │ ───────────────▶ │  Seller Payment System  │
│   (owns orders)     │                  │  (owns payout mapping)  │
└─────────────────────┘                  └─────────────────────────┘
```

Problems with modifying Order table:
- Payment System needs **write access** to OrderService's database
- Creates tight coupling between services
- Different deployment cycles
- Different data retention (payments: 7 years, orders: varies)

### 3. Payment-Specific State Machine

The mapping tracks payment-domain states:

```
PENDING → SETTLED → PAID
    ↓
CANCELLED
```

States like `SETTLED` and `PAID` are payment concepts, not order concepts.

---

## When Could You Use the Order Table?

Adding to Order table works if:
- ✅ Single seller per order
- ✅ Monolithic architecture (same service owns both)
- ✅ Shared database is acceptable
- ✅ Coupling between Order and Payment domains is okay

---

## Comparison

| Aspect | Separate Mapping Table | Add to Order Table |
|--------|----------------------|-------------------|
| Multi-seller orders | ✅ Handles naturally | ❌ Requires workaround |
| Microservices | ✅ Clean boundaries | ❌ Cross-service writes |
| Data ownership | ✅ Payment owns its data | ❌ Shared ownership |
| Query complexity | More joins | Simpler queries |
| Best for | Microservices, multi-seller | Monolith, single-seller |

---

## Alternative: Minimal Mapping Table

If reducing duplication is important, store only seller-specific data:

```sql
CREATE TABLE order_seller_payout (
    order_id        VARCHAR(50) NOT NULL,  -- Reference only
    seller_id       VARCHAR(50) NOT NULL,
    seller_amount   DECIMAL(15,2) NOT NULL,
    status          VARCHAR(20) NOT NULL,
    payout_id       VARCHAR(100),
    settlement_date TIMESTAMP,
    PRIMARY KEY (order_id, seller_id)
);
```

Fetch order details (timestamp, etc.) from OrderService via API when needed.

---

## Conclusion

The separate `ORDER_PAYOUT_MAPPING` table exists because:
1. **Cardinality**: 1 order → N sellers → N payout mappings
2. **Service boundaries**: Payment system owns payment data
3. **Domain separation**: Payment states don't belong in Order entity

