# Agoda: Lexicographically Smallest Substring with k `1`s

## Problem

Given a binary string `s` and an integer `k`, return the lexicographically smallest contiguous substring that contains exactly `k` occurrences of `1`. If `k` ≤ 0, the string is null/empty, or `s` has fewer than `k` ones, return the empty string.

---

## Key Insight: Why Leading Zeros Matter

In lexicographic ordering, `'0' < '1'`. So a string starting with `0` is always smaller than one starting with `1`:

- `"011" < "101" < "110"`

**Strategy**: For each group of k consecutive `1`s, include as many leading `0`s as possible without adding extra `1`s.

---

## Algorithm (Step-by-Step)

### Step 1: Find All `1` Positions

Scan the string once and store the index of every `'1'` character.

```java
List<Integer> onesPositions = new ArrayList<>();
for (int i = 0; i < inputStr.length(); i++) {
    if (inputStr.charAt(i) == '1') {
        onesPositions.add(i);
    }
}
```

### Step 2: Early Exit Check

If the number of `1`s found is less than `k`, no valid substring exists → return `""`.

### Step 3: Sliding Window Over `1` Positions

Instead of sliding over the string, we slide over the **list of `1` positions** in windows of size `k`.

For each window `i` (where `i` ranges from `0` to `onesPositions.size() - k`):

**Start Position:**

```java
int start = (i == 0) ? 0 : onesPositions.get(i - 1) + 1;
```

- For the **first window** (`i == 0`): start at index `0` to capture all leading zeros.
- For **subsequent windows**: start right **after the previous `1`** (at index `onesPositions.get(i-1) + 1`). This ensures we don't include the previous `1` (which would give us k+1 ones).

**End Position:**

```java
int end = onesPositions.get(i + k - 1) + 1;  // +1 because substring is exclusive
```

- End at the k-th `1` in this window (the `1` at index `i + k - 1` in our positions list).

**Extract & Compare:**

```java
String candidate = inputStr.substring(start, end);
if (smallest == null || candidate.compareTo(smallest) < 0) {
    smallest = candidate;
}
```

---

## Dry Run: `"111000111"`, k = 3

### Step 1: Find `1` Positions

| String Index | 0   | 1   | 2   | 3   | 4   | 5   | 6   | 7   | 8   |
| ------------ | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Character    | 1   | 1   | 1   | 0   | 0   | 0   | 1   | 1   | 1   |

**onesPositions = [0, 1, 2, 6, 7, 8]** (6 ones total)

### Step 2: Check

6 ones ≥ k=3 ✓ → proceed

### Step 3: Sliding Window (size k=3)

Number of windows = 6 - 3 + 1 = **4 windows**

---

#### Window i=0: First 3 ones at positions [0, 1, 2]

| Calculation | Value                                                                           |
| ----------- | ------------------------------------------------------------------------------- |
| start       | `i == 0` → **0**                                                                |
| end         | `onesPositions.get(0 + 3 - 1) + 1` = `onesPositions.get(2) + 1` = **2 + 1 = 3** |
| candidate   | `substring(0, 3)` = **"111"**                                                   |

---

#### Window i=1: Ones at positions [1, 2, 6]

| Calculation | Value                                                                           |
| ----------- | ------------------------------------------------------------------------------- |
| start       | `onesPositions.get(i - 1) + 1` = `onesPositions.get(0) + 1` = **0 + 1 = 1**     |
| end         | `onesPositions.get(1 + 3 - 1) + 1` = `onesPositions.get(3) + 1` = **6 + 1 = 7** |
| candidate   | `substring(1, 7)` = **"110001"**                                                |

Compare: `"110001".compareTo("111")` → `'0' < '1'` at index 2 → **"110001" < "111"**
→ smallest = "110001"

---

#### Window i=2: Ones at positions [2, 6, 7]

| Calculation | Value                                                                           |
| ----------- | ------------------------------------------------------------------------------- |
| start       | `onesPositions.get(1) + 1` = **1 + 1 = 2**                                      |
| end         | `onesPositions.get(2 + 3 - 1) + 1` = `onesPositions.get(4) + 1` = **7 + 1 = 8** |
| candidate   | `substring(2, 8)` = **"100011"**                                                |

Compare: `"100011".compareTo("110001")` → `'0' < '1'` at index 1 → **"100011" < "110001"**
→ smallest = "100011"

---

#### Window i=3: Ones at positions [6, 7, 8]

| Calculation | Value                                                                           |
| ----------- | ------------------------------------------------------------------------------- |
| start       | `onesPositions.get(2) + 1` = **2 + 1 = 3**                                      |
| end         | `onesPositions.get(3 + 3 - 1) + 1` = `onesPositions.get(5) + 1` = **8 + 1 = 9** |
| candidate   | `substring(3, 9)` = **"000111"**                                                |

Compare: `"000111".compareTo("100011")` → `'0' < '1'` at index 0 → **"000111" < "100011"**
→ smallest = "000111"

---

### Final Result: **"000111"** ✓

---

## Visual Summary of Windows

```
String:     1 1 1 0 0 0 1 1 1
Index:      0 1 2 3 4 5 6 7 8

Window 0:  [1 1 1]                    → "111"
Window 1:    [1 1 0 0 0 1]            → "110001"
Window 2:      [1 0 0 0 1 1]          → "100011"
Window 3:        [0 0 0 1 1 1]        → "000111" ← WINNER
```

---

## Complexity

- **Time**: O(n) to gather `1` positions + O(m·L) to compare `m = (#ones - k + 1)` candidates of average length `L`.
- **Space**: O(#ones) for storing indices.

---

## Edge Cases Handled

- `null` or empty string → return `""`
- `k ≤ 0` → return `""`
- Fewer than `k` ones in string → return `""`

---

## Alternative: `mySolution` (Brute Force)

The `mySolution` method shows a quadratic O(n²) approach:

- For each starting index, build a substring until exactly k ones are found.
- Store all such substrings, then find the minimum.

This works but is less efficient. Kept for comparison.

---

## Sample Tests

| Input         | k   | Output     | Explanation                                              |
| ------------- | --- | ---------- | -------------------------------------------------------- |
| `"0101101"`   | 3   | `"01011"`  | Windows: `"01011"`, `"1011"`, `"101"` → min is `"01011"` |
| `"1011"`      | 2   | `"011"`    | Windows: `"10"`, `"011"` → min is `"011"`                |
| `"0111"`      | 2   | `"011"`    | Windows: `"011"`, `"11"` → min is `"011"`                |
| `"111000111"` | 3   | `"000111"` | See dry run above                                        |
