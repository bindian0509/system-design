# Coding Patterns & Problem Guide

> **Goal**: Pattern-based preparation, not random grinding
> **Target**: 50 curated problems covering essential patterns
> **Time**: 2 hours daily, 6 weeks to cover all

---

## Pattern Overview

| Pattern | # Problems | Priority | Frequency in Interviews |
|---------|------------|----------|------------------------|
| Arrays & Hashing | 6 | High | ⭐⭐⭐⭐⭐ |
| Two Pointers | 5 | High | ⭐⭐⭐⭐ |
| Sliding Window | 5 | High | ⭐⭐⭐⭐⭐ |
| Stack | 4 | Medium | ⭐⭐⭐ |
| Binary Search | 5 | High | ⭐⭐⭐⭐ |
| Linked List | 4 | Medium | ⭐⭐⭐ |
| Trees | 6 | High | ⭐⭐⭐⭐⭐ |
| Graphs | 5 | High | ⭐⭐⭐⭐ |
| Dynamic Programming | 6 | Medium | ⭐⭐⭐ |
| Intervals | 4 | Medium | ⭐⭐⭐⭐ |

---

## Pattern 1: Arrays & Hashing

### Key Concepts
- Use hashmap for O(1) lookups
- Counting frequencies
- Two-pass vs one-pass solutions

### Problems

| # | Problem | Difficulty | Company Tags | Status |
|---|---------|------------|--------------|--------|
| 1 | [Two Sum](https://leetcode.com/problems/two-sum/) | Easy | All companies | ⬜ |
| 2 | [Contains Duplicate](https://leetcode.com/problems/contains-duplicate/) | Easy | Google, Amazon | ⬜ |
| 3 | [Group Anagrams](https://leetcode.com/problems/group-anagrams/) | Medium | Amazon, Meta | ⬜ |
| 4 | [Top K Frequent Elements](https://leetcode.com/problems/top-k-frequent-elements/) | Medium | Amazon, Meta | ⬜ |
| 5 | [Product of Array Except Self](https://leetcode.com/problems/product-of-array-except-self/) | Medium | Amazon, Microsoft | ⬜ |
| 6 | [Longest Consecutive Sequence](https://leetcode.com/problems/longest-consecutive-sequence/) | Medium | Google, Amazon | ⬜ |

### Template Code
```python
# Two Sum Pattern - Use hashmap for complement lookup
def two_sum(nums, target):
    seen = {}  # value -> index
    for i, num in enumerate(nums):
        complement = target - num
        if complement in seen:
            return [seen[complement], i]
        seen[num] = i
    return []

# Frequency Count Pattern
from collections import Counter
def top_k_frequent(nums, k):
    count = Counter(nums)
    return [x for x, _ in count.most_common(k)]
```

---

## Pattern 2: Two Pointers

### Key Concepts
- Opposite ends (sorted arrays)
- Same direction (fast/slow)
- Three pointers for triplets

### Problems

| # | Problem | Difficulty | Company Tags | Status |
|---|---------|------------|--------------|--------|
| 7 | [Valid Palindrome](https://leetcode.com/problems/valid-palindrome/) | Easy | Meta, Amazon | ⬜ |
| 8 | [3Sum](https://leetcode.com/problems/3sum/) | Medium | Amazon, Google | ⬜ |
| 9 | [Container With Most Water](https://leetcode.com/problems/container-with-most-water/) | Medium | Amazon, Google | ⬜ |
| 10 | [Trapping Rain Water](https://leetcode.com/problems/trapping-rain-water/) | Hard | Amazon, Google | ⬜ |
| 11 | [Move Zeroes](https://leetcode.com/problems/move-zeroes/) | Easy | Meta, Bloomberg | ⬜ |

### Template Code
```python
# Two pointers from opposite ends
def two_pointers_opposite(arr):
    left, right = 0, len(arr) - 1
    while left < right:
        # Process based on condition
        if condition:
            left += 1
        else:
            right -= 1

# Three pointers (3Sum pattern)
def three_sum(nums):
    nums.sort()
    result = []
    for i in range(len(nums) - 2):
        if i > 0 and nums[i] == nums[i-1]:
            continue  # Skip duplicates
        left, right = i + 1, len(nums) - 1
        while left < right:
            total = nums[i] + nums[left] + nums[right]
            if total < 0:
                left += 1
            elif total > 0:
                right -= 1
            else:
                result.append([nums[i], nums[left], nums[right]])
                left += 1
                right -= 1
                while left < right and nums[left] == nums[left-1]:
                    left += 1
    return result
```

---

## Pattern 3: Sliding Window

### Key Concepts
- Fixed size window
- Variable size window (shrink when invalid)
- Use hashmap for window contents

### Problems

| # | Problem | Difficulty | Company Tags | Status |
|---|---------|------------|--------------|--------|
| 12 | [Best Time to Buy and Sell Stock](https://leetcode.com/problems/best-time-to-buy-and-sell-stock/) | Easy | Amazon, Meta | ⬜ |
| 13 | [Longest Substring Without Repeating Characters](https://leetcode.com/problems/longest-substring-without-repeating-characters/) | Medium | Amazon, Google | ⬜ |
| 14 | [Longest Repeating Character Replacement](https://leetcode.com/problems/longest-repeating-character-replacement/) | Medium | Google, Amazon | ⬜ |
| 15 | [Minimum Window Substring](https://leetcode.com/problems/minimum-window-substring/) | Hard | Meta, Amazon | ⬜ |
| 16 | [Sliding Window Maximum](https://leetcode.com/problems/sliding-window-maximum/) | Hard | Amazon, Google | ⬜ |

### Template Code
```python
# Variable size sliding window
def sliding_window_variable(s):
    window = {}  # or set for unique elements
    left = 0
    result = 0

    for right in range(len(s)):
        # Expand window - add s[right] to window
        window[s[right]] = window.get(s[right], 0) + 1

        # Shrink window while invalid
        while not is_valid(window):
            window[s[left]] -= 1
            if window[s[left]] == 0:
                del window[s[left]]
            left += 1

        # Update result
        result = max(result, right - left + 1)

    return result
```

---

## Pattern 4: Stack

### Key Concepts
- Monotonic stack for next greater/smaller
- Parentheses matching
- Expression evaluation

### Problems

| # | Problem | Difficulty | Company Tags | Status |
|---|---------|------------|--------------|--------|
| 17 | [Valid Parentheses](https://leetcode.com/problems/valid-parentheses/) | Easy | Amazon, Meta | ⬜ |
| 18 | [Min Stack](https://leetcode.com/problems/min-stack/) | Medium | Amazon, Microsoft | ⬜ |
| 19 | [Daily Temperatures](https://leetcode.com/problems/daily-temperatures/) | Medium | Amazon, Google | ⬜ |
| 20 | [Largest Rectangle in Histogram](https://leetcode.com/problems/largest-rectangle-in-histogram/) | Hard | Amazon, Google | ⬜ |

### Template Code
```python
# Monotonic decreasing stack (next greater element)
def next_greater(nums):
    n = len(nums)
    result = [-1] * n
    stack = []  # stores indices

    for i in range(n):
        while stack and nums[i] > nums[stack[-1]]:
            idx = stack.pop()
            result[idx] = nums[i]
        stack.append(i)

    return result
```

---

## Pattern 5: Binary Search

### Key Concepts
- Search space reduction
- Finding boundaries (leftmost, rightmost)
- Search on answer (monotonic function)

### Problems

| # | Problem | Difficulty | Company Tags | Status |
|---|---------|------------|--------------|--------|
| 21 | [Binary Search](https://leetcode.com/problems/binary-search/) | Easy | All | ⬜ |
| 22 | [Search in Rotated Sorted Array](https://leetcode.com/problems/search-in-rotated-sorted-array/) | Medium | Amazon, Meta | ⬜ |
| 23 | [Find Minimum in Rotated Sorted Array](https://leetcode.com/problems/find-minimum-in-rotated-sorted-array/) | Medium | Amazon, Microsoft | ⬜ |
| 24 | [Koko Eating Bananas](https://leetcode.com/problems/koko-eating-bananas/) | Medium | Google, Amazon | ⬜ |
| 25 | [Median of Two Sorted Arrays](https://leetcode.com/problems/median-of-two-sorted-arrays/) | Hard | Google, Amazon | ⬜ |

### Template Code
```python
# Standard binary search
def binary_search(nums, target):
    left, right = 0, len(nums) - 1
    while left <= right:
        mid = left + (right - left) // 2
        if nums[mid] == target:
            return mid
        elif nums[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    return -1

# Binary search on answer (when to use: find minimum X such that condition(X) is true)
def binary_search_answer(lo, hi, condition):
    while lo < hi:
        mid = lo + (hi - lo) // 2
        if condition(mid):
            hi = mid  # answer could be mid or smaller
        else:
            lo = mid + 1  # answer must be larger
    return lo
```

---

## Pattern 6: Linked List

### Key Concepts
- Fast/slow pointers (cycle detection, middle)
- Dummy head for edge cases
- Reversal in-place

### Problems

| # | Problem | Difficulty | Company Tags | Status |
|---|---------|------------|--------------|--------|
| 26 | [Reverse Linked List](https://leetcode.com/problems/reverse-linked-list/) | Easy | All | ⬜ |
| 27 | [Linked List Cycle](https://leetcode.com/problems/linked-list-cycle/) | Easy | Amazon, Microsoft | ⬜ |
| 28 | [Merge Two Sorted Lists](https://leetcode.com/problems/merge-two-sorted-lists/) | Easy | Amazon, Microsoft | ⬜ |
| 29 | [LRU Cache](https://leetcode.com/problems/lru-cache/) | Medium | Amazon, Meta | ⬜ |

### Template Code
```python
# Reverse linked list
def reverse(head):
    prev = None
    curr = head
    while curr:
        next_temp = curr.next
        curr.next = prev
        prev = curr
        curr = next_temp
    return prev

# Floyd's cycle detection
def has_cycle(head):
    slow = fast = head
    while fast and fast.next:
        slow = slow.next
        fast = fast.next.next
        if slow == fast:
            return True
    return False
```

---

## Pattern 7: Trees

### Key Concepts
- DFS (preorder, inorder, postorder)
- BFS (level order)
- Recursion patterns

### Problems

| # | Problem | Difficulty | Company Tags | Status |
|---|---------|------------|--------------|--------|
| 30 | [Maximum Depth of Binary Tree](https://leetcode.com/problems/maximum-depth-of-binary-tree/) | Easy | Amazon, Google | ⬜ |
| 31 | [Invert Binary Tree](https://leetcode.com/problems/invert-binary-tree/) | Easy | Google | ⬜ |
| 32 | [Validate Binary Search Tree](https://leetcode.com/problems/validate-binary-search-tree/) | Medium | Amazon, Meta | ⬜ |
| 33 | [Binary Tree Level Order Traversal](https://leetcode.com/problems/binary-tree-level-order-traversal/) | Medium | Amazon, Meta | ⬜ |
| 34 | [Lowest Common Ancestor of a Binary Tree](https://leetcode.com/problems/lowest-common-ancestor-of-a-binary-tree/) | Medium | Amazon, Meta | ⬜ |
| 35 | [Serialize and Deserialize Binary Tree](https://leetcode.com/problems/serialize-and-deserialize-binary-tree/) | Hard | Amazon, Meta | ⬜ |

### Template Code
```python
# DFS - Recursive
def max_depth(root):
    if not root:
        return 0
    return 1 + max(max_depth(root.left), max_depth(root.right))

# BFS - Level order
from collections import deque
def level_order(root):
    if not root:
        return []
    result = []
    queue = deque([root])
    while queue:
        level_size = len(queue)
        level = []
        for _ in range(level_size):
            node = queue.popleft()
            level.append(node.val)
            if node.left:
                queue.append(node.left)
            if node.right:
                queue.append(node.right)
        result.append(level)
    return result
```

---

## Pattern 8: Graphs

### Key Concepts
- DFS/BFS traversal
- Cycle detection
- Topological sort
- Union-Find

### Problems

| # | Problem | Difficulty | Company Tags | Status |
|---|---------|------------|--------------|--------|
| 36 | [Number of Islands](https://leetcode.com/problems/number-of-islands/) | Medium | Amazon, Google | ⬜ |
| 37 | [Clone Graph](https://leetcode.com/problems/clone-graph/) | Medium | Meta, Amazon | ⬜ |
| 38 | [Course Schedule](https://leetcode.com/problems/course-schedule/) | Medium | Amazon, Microsoft | ⬜ |
| 39 | [Pacific Atlantic Water Flow](https://leetcode.com/problems/pacific-atlantic-water-flow/) | Medium | Google, Amazon | ⬜ |
| 40 | [Word Ladder](https://leetcode.com/problems/word-ladder/) | Hard | Amazon, Meta | ⬜ |

### Template Code
```python
# BFS for graphs
from collections import deque
def bfs(graph, start):
    visited = {start}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        for neighbor in graph[node]:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)

# DFS for graphs
def dfs(graph, node, visited):
    visited.add(node)
    for neighbor in graph[node]:
        if neighbor not in visited:
            dfs(graph, neighbor, visited)

# Topological Sort (Kahn's algorithm)
from collections import deque
def topological_sort(num_nodes, prerequisites):
    indegree = [0] * num_nodes
    graph = [[] for _ in range(num_nodes)]

    for dest, src in prerequisites:
        graph[src].append(dest)
        indegree[dest] += 1

    queue = deque([i for i in range(num_nodes) if indegree[i] == 0])
    order = []

    while queue:
        node = queue.popleft()
        order.append(node)
        for neighbor in graph[node]:
            indegree[neighbor] -= 1
            if indegree[neighbor] == 0:
                queue.append(neighbor)

    return order if len(order) == num_nodes else []
```

---

## Pattern 9: Dynamic Programming

### Key Concepts
- Identify subproblems
- Memoization vs tabulation
- State transition

### Problems

| # | Problem | Difficulty | Company Tags | Status |
|---|---------|------------|--------------|--------|
| 41 | [Climbing Stairs](https://leetcode.com/problems/climbing-stairs/) | Easy | Amazon, Google | ⬜ |
| 42 | [House Robber](https://leetcode.com/problems/house-robber/) | Medium | Amazon, Google | ⬜ |
| 43 | [Coin Change](https://leetcode.com/problems/coin-change/) | Medium | Amazon, Microsoft | ⬜ |
| 44 | [Longest Increasing Subsequence](https://leetcode.com/problems/longest-increasing-subsequence/) | Medium | Amazon, Google | ⬜ |
| 45 | [Unique Paths](https://leetcode.com/problems/unique-paths/) | Medium | Amazon, Google | ⬜ |
| 46 | [Edit Distance](https://leetcode.com/problems/edit-distance/) | Medium | Amazon, Google | ⬜ |

### Template Code
```python
# 1D DP - Bottom-up
def climb_stairs(n):
    if n <= 2:
        return n
    dp = [0] * (n + 1)
    dp[1], dp[2] = 1, 2
    for i in range(3, n + 1):
        dp[i] = dp[i-1] + dp[i-2]
    return dp[n]

# 2D DP - Edit distance
def edit_distance(word1, word2):
    m, n = len(word1), len(word2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if word1[i-1] == word2[j-1]:
                dp[i][j] = dp[i-1][j-1]
            else:
                dp[i][j] = 1 + min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1])

    return dp[m][n]
```

---

## Pattern 10: Intervals

### Key Concepts
- Sort by start or end
- Merge overlapping
- Meeting rooms pattern

### Problems

| # | Problem | Difficulty | Company Tags | Status |
|---|---------|------------|--------------|--------|
| 47 | [Merge Intervals](https://leetcode.com/problems/merge-intervals/) | Medium | Amazon, Google | ⬜ |
| 48 | [Insert Interval](https://leetcode.com/problems/insert-interval/) | Medium | Google, Amazon | ⬜ |
| 49 | [Non-overlapping Intervals](https://leetcode.com/problems/non-overlapping-intervals/) | Medium | Amazon, Microsoft | ⬜ |
| 50 | [Meeting Rooms II](https://leetcode.com/problems/meeting-rooms-ii/) | Medium | Amazon, Google | ⬜ |

### Template Code
```python
# Merge intervals
def merge_intervals(intervals):
    intervals.sort(key=lambda x: x[0])
    merged = [intervals[0]]

    for start, end in intervals[1:]:
        if start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])

    return merged
```

---

## Daily Practice Schedule

### Week 1-2: Fundamentals
| Day | Pattern | Problems |
|-----|---------|----------|
| Day 1 | Arrays & Hashing | #1, #2, #3 |
| Day 2 | Arrays & Hashing | #4, #5, #6 |
| Day 3 | Two Pointers | #7, #8, #9 |
| Day 4 | Two Pointers | #10, #11 |
| Day 5 | Sliding Window | #12, #13, #14 |
| Day 6 | Sliding Window | #15, #16 |
| Day 7 | Review Week 1 | Redo any unsolved |

### Week 3-4: Core Patterns
| Day | Pattern | Problems |
|-----|---------|----------|
| Day 8 | Stack | #17, #18 |
| Day 9 | Stack | #19, #20 |
| Day 10 | Binary Search | #21, #22, #23 |
| Day 11 | Binary Search | #24, #25 |
| Day 12 | Linked List | #26, #27, #28 |
| Day 13 | Linked List | #29 |
| Day 14 | Review Week 2 | Redo any unsolved |

### Week 5-6: Advanced Patterns
| Day | Pattern | Problems |
|-----|---------|----------|
| Day 15 | Trees | #30, #31, #32 |
| Day 16 | Trees | #33, #34, #35 |
| Day 17 | Graphs | #36, #37 |
| Day 18 | Graphs | #38, #39, #40 |
| Day 19 | DP | #41, #42, #43 |
| Day 20 | DP | #44, #45, #46 |
| Day 21 | Intervals | #47, #48, #49, #50 |

### Week 7+: Mock Interviews
- Do timed practice (45 min for 2 problems)
- Practice explaining your thought process
- Use platforms like Pramp or interviewing.io

---

## Progress Tracker

| Pattern | Total | Solved | Easy | Medium | Hard |
|---------|-------|--------|------|--------|------|
| Arrays & Hashing | 6 | 0 | 2 | 4 | 0 |
| Two Pointers | 5 | 0 | 2 | 2 | 1 |
| Sliding Window | 5 | 0 | 1 | 2 | 2 |
| Stack | 4 | 0 | 1 | 2 | 1 |
| Binary Search | 5 | 0 | 1 | 3 | 1 |
| Linked List | 4 | 0 | 3 | 1 | 0 |
| Trees | 6 | 0 | 2 | 3 | 1 |
| Graphs | 5 | 0 | 0 | 4 | 1 |
| DP | 6 | 0 | 1 | 5 | 0 |
| Intervals | 4 | 0 | 0 | 4 | 0 |
| **Total** | **50** | **0** | **13** | **30** | **7** |

---

## Complexity Cheat Sheet

| Operation | Array | LinkedList | HashTable | BST | Heap |
|-----------|-------|------------|-----------|-----|------|
| Access | O(1) | O(n) | O(1) | O(log n) | O(1)* |
| Search | O(n) | O(n) | O(1) | O(log n) | O(n) |
| Insert | O(n) | O(1) | O(1) | O(log n) | O(log n) |
| Delete | O(n) | O(1) | O(1) | O(log n) | O(log n) |

*Heap: O(1) for min/max only

