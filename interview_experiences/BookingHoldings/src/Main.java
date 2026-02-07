import java.io.*;
import java.util.*;
import java.text.*;
import java.math.*;
import java.util.regex.*;

public class Main {

    public static Map<Integer, Map<String, Integer>> getFlights(int startDay, int endDay) {
        // Dummy data: day -> price mapping for the test case getCheapestFlights(3, 3, 8)
        // Day:   3    4    5    6    7    8
        // Price: 100  300  500  500  200  100
        Map<Integer, Integer> priceData = new HashMap<>();
        priceData.put(3, 100);
        priceData.put(4, 300);
        priceData.put(5, 500);
        priceData.put(6, 500);
        priceData.put(7, 200);
        priceData.put(8, 100);

        Map<Integer, Map<String, Integer>> flights = new HashMap<>();
        for (int day = startDay; day <= endDay; day++) {
            Map<String, Integer> entry = new HashMap<>();
            entry.put("price", priceData.getOrDefault(day, 0));
            flights.put(day, entry);
        }
        return flights;
    }

    public static void main(String[] args) {
        Map<String, Map<String, Integer>> result = getCheapestFlights(3, 3, 8);
        System.out.println("Result:");
        for (Map.Entry<String, Map<String, Integer>> e : result.entrySet()) {
            System.out.println("  " + e.getKey() + ": " + e.getValue());
        }
    }

    public static Map<String, Map<String, Integer>> getCheapestFlights(int dayRange, int startDay, int endDay) {

        // Step 1: Fetch all flight data (assume getFlights is implemented)
        Map<Integer, Map<String, Integer>> flights = getFlights(startDay, endDay);

        //Using LinkedHashMap here is a stylistic choice to preserve insertion order
        // — so the output keys appear in the natural window
        // order ("3-5", "4-6", "5-7", "6-8") rather than in an arbitrary hash-bucket order.
        Map<String, Map<String, Integer>> result = new LinkedHashMap<>();

        // Step 2: Monotonic deque — stores day numbers; front always holds the cheapest day in the window
        Deque<Integer> deque = new ArrayDeque<>();

        for (int day = startDay; day <= endDay; day++) {
            int price = flights.get(day).get("price");

            // Remove from back: any day whose price >= current price can never be the min
            while (!deque.isEmpty() && flights.get(deque.peekLast()).get("price") >= price) {
                deque.pollLast();
            }
            deque.addLast(day);

            // Remove from front: any day that has fallen out of the current window
            while (deque.peekFirst() < day - dayRange + 1) {
                deque.pollFirst();
            }

            // Once we have a full window of size dayRange, record the result
            if (day >= startDay + dayRange - 1) {
                int windowStart = day - dayRange + 1;
                String rangeKey = windowStart + "-" + day;

                int minDay = deque.peekFirst();
                int minPrice = flights.get(minDay).get("price");

                Map<String, Integer> entry = new HashMap<>();
                entry.put("day", minDay);
                entry.put("price", minPrice);
                result.put(rangeKey, entry);
            }
        }

        return result;
    }
}
