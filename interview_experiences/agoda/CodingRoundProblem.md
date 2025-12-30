## Code Snippet for the problem 


```java

import java.util.ArrayList;
import java.util.List;

/**
 * @author : Bharat V.
 * @created : Thursday December 18, 2025 8:01 pm
 *
 * Find the lexicographically smallest substring containing exactly k 1s.
 *
 * Approach:
 * 1. Find all positions of 1s in the string
 * 2. For each window of k consecutive 1s, the optimal substring starts
 *    right after the previous 1 (to include leading 0s, making it smaller)
 *    and ends at the k-th 1 of that window
 * 3. Compare all such candidates and return the smallest
 *
 * Time Complexity: O(n) for finding positions + O(m * L) for comparisons
 *                  where m = number of windows, L = average substring length
 * Space Complexity: O(number of 1s) for storing positions
 */

public class AgodaLexicographicallySmallString {

    public static String lexicographicallySmallestSubStringWithKNumberOf1s(String inputStr, int k) {
        if (inputStr == null || inputStr.isEmpty() || k <= 0) {
            return "";
        }

        // Step 1: Find all positions of 1s
        List<Integer> onesPositions = new ArrayList<>();
        for (int i = 0; i < inputStr.length(); i++) {
            if (inputStr.charAt(i) == '1') {
                onesPositions.add(i);
            }
        }

        // If there are fewer than k 1s, no valid substring exists
        if (onesPositions.size() < k) {
            return "";
        }

        String smallest = null;

        // Step 2: For each window of k consecutive 1s, find the candidate substring
        // Number of windows = (total 1s) - k + 1
        for (int i = 0; i <= onesPositions.size() - k; i++) {
            // Start right after the previous 1, or at index 0 for the first window
            // This ensures we include all leading 0s (making it lexicographically smaller)
            int start = (i == 0) ? 0 : onesPositions.get(i - 1) + 1;

            // End at the k-th 1 in this window (inclusive, so +1 for substring)
            int end = onesPositions.get(i + k - 1) + 1;

            String candidate = inputStr.substring(start, end);

            // Step 3: Track the lexicographically smallest
            if (smallest == null || candidate.compareTo(smallest) < 0) {
                smallest = candidate;
            }
        }

        return smallest;
    }
    public static String mySolution (String input_str, int k) {
        ArrayList<String> result = new ArrayList<>();

        int j = 0;
        for (int i = 0; i < input_str.length(); i++) {
            j = i;
            StringBuilder sb = new StringBuilder();
            int tempK = 0;
            if (input_str.length()-j+1 > k) {
                while (j < input_str.length()) {
                    if (input_str.charAt(j) == '1') {
                        tempK++;
                    }
                    sb.append(input_str.charAt(j));
                    j++;
                    if (tempK == k) {
                        result.add(sb.toString());
                        break;
                    }
                }
            }
        }

        String smallestLexi = result.get(0);
        for (String str : result) {
            // MISSED THIS PART WHERE I DONT KNOW HOW TO CHECK LEXICOGRAPHICALLY COMPARISON
            if(str.compareTo(smallestLexi) < 0)
                smallestLexi = str;
        }

        System.out.println(result);
        return smallestLexi;
    }
    public static void main(String[] args) {
        // Test cases
        System.out.println("Test 1: '0101101', k=3");
        System.out.println("Result: " + lexicographicallySmallestSubStringWithKNumberOf1s("0101101", 3));
        // Expected: "01011" (positions 0-4, 1s at indices 1,3,4)

        System.out.println("\nTest 2: '1011', k=2");
        System.out.println("Result: " + lexicographicallySmallestSubStringWithKNumberOf1s("1011", 2));
        // Expected: "011" (positions 1-3, 1s at indices 2,3)

        System.out.println("\nTest 3: '0111', k=2");
        System.out.println("Result: " + lexicographicallySmallestSubStringWithKNumberOf1s("0111", 2));
        // Expected: "011" (positions 0-2, 1s at indices 1,2)

        System.out.println("\nTest 4: '111000111', k=3");
        System.out.println("Result: " + lexicographicallySmallestSubStringWithKNumberOf1s("111000111", 3));
        // Expected: "000111" (positions 3-8, 1s at indices 6,7,8)
    }
}
```