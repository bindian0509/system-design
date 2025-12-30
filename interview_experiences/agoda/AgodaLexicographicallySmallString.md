# Agoda: Lexicographically Smallest Substring with k `1`s

## Problem
Given a binary string `s` and an integer `k`, return the lexicographically smallest contiguous substring that contains exactly `k` occurrences of `1`. If `k` ≤ 0, the string is null/empty, or `s` has fewer than `k` ones, return the empty string.

## Approach (implemented in `lexicographicallySmallestSubStringWithKNumberOf1s`)
- Collect indices of all `1` characters.
- If the list has fewer than `k` entries, no solution exists.
- Slide a window of size `k` over the indices of `1`s. For each window:
  - Start index: right after the previous `1` (or `0` for the first window) so leading zeros are included, which makes the substring lexicographically smaller.
  - End index: the position of the window’s `k`-th `1` (inclusive), so substring bounds are `[start, end]`.
  - Extract the candidate substring and keep the lexicographically smallest via `String.compareTo`.
- Return the best candidate.

## Complexity
- Time: O(n) to gather `1` positions plus O(m·L) to compare `m = (#ones - k + 1)` candidates of average length `L`.
- Space: O(#ones) for storing indices.

## Notes
- Includes fast exits for bad inputs (`null`, empty, or `k` ≤ 0).
- `mySolution` shows an initial quadratic attempt (builds every substring starting at each index until `k` ones are seen); kept for comparison but not used in the main flow.

## Sample tests (from `main`)
- `"0101101", k=3` → `"01011"`
- `"1011", k=2` → `"011"`
- `"0111", k=2` → `"011"`
- `"111000111", k=3` → `"000111"`


