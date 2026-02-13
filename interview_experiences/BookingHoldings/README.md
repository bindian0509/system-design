# Cheapest Flights in a Sliding Window

## Problem Statement

Given a range of days (`startDay` to `endDay`), each with a flight price, find the **cheapest flight (day and price)** for every consecutive window of `dayRange` days.

### Function Signature

```java
Map<String, Map<String, Integer>> getCheapestFlights(int dayRange, int startDay, int endDay)
```

### Example

```
getCheapestFlights(3, 3, 8)

Day:     3    4    5    6    7    8
Price:  100  300  500  500  200  100

Window "3-5" → days [3,4,5] → prices [100,300,500] → cheapest: day 3, price 100
Window "4-6" → days [4,5,6] → prices [300,500,500] → cheapest: day 4, price 300
Window "5-7" → days [5,6,7] → prices [500,500,200] → cheapest: day 7, price 200
Window "6-8" → days [6,7,8] → prices [500,200,100] → cheapest: day 8, price 100
```

### Expected Output

```
{
  "3-5": {"day": 3, "price": 100},
  "4-6": {"day": 4, "price": 300},
  "5-7": {"day": 7, "price": 200},
  "6-8": {"day": 8, "price": 100}
}
```

---

## Approach 1 — Brute Force

For each window, iterate through all `dayRange` elements and find the minimum.

```java
for (int i = startDay; i <= endDay - dayRange + 1; i++) {
    int minPrice = Integer.MAX_VALUE;
    int minDay = i;
    for (int j = i; j < i + dayRange; j++) {
        if (flights.get(j).get("price") < minPrice) {
            minPrice = flights.get(j).get("price");
            minDay = j;
        }
    }
    // store result for window i to i+dayRange-1
}
```

### Complexity

| Metric | Value |
|--------|-------|
| Time   | O(n * k) where n = number of days, k = dayRange |
| Space  | O(1) extra (beyond the result map) |

### Pros

- Simple to understand and implement.
- No additional data structures needed.
- Easy to debug and verify correctness.

### Cons

- Redundant work — each element is compared up to `k` times across overlapping windows.
- Becomes slow when `dayRange` is large (e.g., k = 10,000 over n = 100,000 days → 10^9 operations).

---

## Approach 2 — Monotonic Deque (Optimal)

Use a double-ended queue (deque) that maintains day indices in **increasing order of price** from front to back. The front of the deque always holds the index of the cheapest day in the current window.

### Algorithm

1. For each day (left to right):
   - **Remove from back**: pop all days from the deque whose price >= current day's price. They can never be the minimum while the current day is in the window.
   - **Add current day** to the back of the deque.
   - **Remove from front**: pop days that have fallen outside the current window.
   - **Record result**: once a full window is formed, the front of the deque is the answer.

### Why It Works

Each day enters the deque once and leaves at most once (either from the front when it expires, or from the back when a cheaper day arrives). This amortizes to O(1) per day.

### Complexity

| Metric | Value |
|--------|-------|
| Time   | O(n) — each element is pushed and popped at most once |
| Space  | O(k) — the deque holds at most `dayRange` elements |

### Pros

- Optimal time complexity — can't do better since every price must be examined at least once.
- Efficient even for very large inputs (n = 10^6, k = 10^5 is trivial).
- Each element is processed at most twice (one push, one pop).

### Cons

- Slightly more complex to implement and reason about.
- Requires understanding of the monotonic deque pattern.
- Harder to debug if the deque invariant is broken.

### Step-by-Step Visualization — `getCheapestFlights(3, 3, 8)`

```mermaid
flowchart TD
    Start["Start: dayRange=3, startDay=3, endDay=8<br/>Prices → 3:100, 4:300, 5:500, 6:500, 7:200, 8:100<br/>Deque = empty"]

    Start --> D3

    subgraph D3["Day 3 — Price 100"]
        D3A["Back check: deque empty → skip"]
        D3B["Push day 3 → Deque = [3]"]
        D3C["Front check: 3 >= 3-3+1=1 → ok"]
        D3D["Window not full yet (need 3 days)"]
        D3A --> D3B --> D3C --> D3D
    end

    D3 --> D4

    subgraph D4["Day 4 — Price 300"]
        D4A["Back check: price[3]=100 < 300 → keep"]
        D4B["Push day 4 → Deque = [3, 4]"]
        D4C["Front check: 3 >= 4-3+1=2 → ok"]
        D4D["Window not full yet (need 3 days)"]
        D4A --> D4B --> D4C --> D4D
    end

    D4 --> D5

    subgraph D5["Day 5 — Price 500"]
        D5A["Back check: price[4]=300 < 500 → keep"]
        D5B["Push day 5 → Deque = [3, 4, 5]"]
        D5C["Front check: 3 >= 5-3+1=3 → ok"]
        D5D["Window full! Front = day 3"]
        D5E["Result: 3-5 → day=3, price=100"]
        D5A --> D5B --> D5C --> D5D --> D5E
    end

    D5 --> D6

    subgraph D6["Day 6 — Price 500"]
        D6A["Back check: price[5]=500 >= 500 → pop 5<br/>price[4]=300 < 500 → keep"]
        D6B["Push day 6 → Deque = [3, 4, 6]"]
        D6C["Front check: 3 < 6-3+1=4 → pop 3<br/>Deque = [4, 6]"]
        D6D["Window full! Front = day 4"]
        D6E["Result: 4-6 → day=4, price=300"]
        D6A --> D6B --> D6C --> D6D --> D6E
    end

    D6 --> D7

    subgraph D7["Day 7 — Price 200"]
        D7A["Back check: price[6]=500 >= 200 → pop 6<br/>price[4]=300 >= 200 → pop 4<br/>Deque empty → stop"]
        D7B["Push day 7 → Deque = [7]"]
        D7C["Front check: 7 >= 7-3+1=5 → ok"]
        D7D["Window full! Front = day 7"]
        D7E["Result: 5-7 → day=7, price=200"]
        D7A --> D7B --> D7C --> D7D --> D7E
    end

    D7 --> D8

    subgraph D8["Day 8 — Price 100"]
        D8A["Back check: price[7]=200 >= 100 → pop 7<br/>Deque empty → stop"]
        D8B["Push day 8 → Deque = [8]"]
        D8C["Front check: 8 >= 8-3+1=6 → ok"]
        D8D["Window full! Front = day 8"]
        D8E["Result: 6-8 → day=8, price=100"]
        D8A --> D8B --> D8C --> D8D --> D8E
    end

    D8 --> Final

    Final["Final Output:<br/>3-5 → day 3, price 100<br/>4-6 → day 4, price 300<br/>5-7 → day 7, price 200<br/>6-8 → day 8, price 100"]

    style Start fill:#4a90d9,color:#fff
    style Final fill:#2ecc71,color:#fff
    style D5E fill:#27ae60,color:#fff
    style D6E fill:#27ae60,color:#fff
    style D7E fill:#27ae60,color:#fff
    style D8E fill:#27ae60,color:#fff
    style D6A fill:#e74c3c,color:#fff
    style D7A fill:#e74c3c,color:#fff
    style D8A fill:#e74c3c,color:#fff
    style D6C fill:#e67e22,color:#fff
```

---

## Comparison

| Criteria         | Brute Force | Monotonic Deque |
|------------------|-------------|-----------------|
| Time Complexity  | O(n * k)    | O(n)            |
| Space Complexity | O(1)        | O(k)            |
| Implementation   | Simple      | Moderate         |
| Best for         | Small k     | Any input size   |

---

## How to Run

```bash
javac src/Main.java -d out
java -cp out Main
```
