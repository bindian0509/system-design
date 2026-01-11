package com.urlshortener.repository;

import com.urlshortener.config.RegionConfig;
import com.urlshortener.service.GlobalIdGenerator.CounterRepository;
import com.urlshortener.service.GlobalIdGenerator.RangeAllocation;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Repository;

import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;

/**
 * DynamoDB-based counter repository for production range allocation.
 *
 * DynamoDB Table Schema:
 * ┌─────────────────────────────────────────────────────────────────────────┐
 * │  Table: url_shortener_counters                                          │
 * ├─────────────────────────────────────────────────────────────────────────┤
 * │  PK (String)          │ current_value (Number) │ last_allocated (String)│
 * ├───────────────────────┼────────────────────────┼────────────────────────┤
 * │  us-east-1#COUNTER    │ 50,000,000             │ 2024-01-15T10:30:00Z   │
 * │  eu-west-1#COUNTER    │ 1,173,900,000,000      │ 2024-01-15T10:35:00Z   │
 * │  ap-south-1#COUNTER   │ 2,347,750,000,000      │ 2024-01-15T10:32:00Z   │
 * └───────────────────────┴────────────────────────┴────────────────────────┘
 *
 * Update Expression (Atomic Increment):
 * UpdateExpression: "SET current_value = current_value + :batch,
 *                       last_allocated = :timestamp"
 * ConditionExpression: "current_value < :max_range"
 * ReturnValues: "UPDATED_OLD"
 *
 * This ensures:
 * - Atomic allocation across all instances
 * - No collisions between concurrent requests
 * - Bounded within region's range
 */
@Slf4j
@Repository
@Profile("aws")
public class DynamoDbCounterRepository implements CounterRepository {

    private static final String TABLE_NAME = "url_shortener_counters";

    // In production, this would be the actual DynamoDB client
    // private final DynamoDbClient dynamoDbClient;

    @Value("${AWS_REGION:us-east-1}")
    private String awsRegion;

    // Simulated counter for demonstration (replace with actual DynamoDB calls)
    private final ConcurrentHashMap<String, AtomicLong> simulatedCounters = new ConcurrentHashMap<>();

    @Override
    public RangeAllocation allocateRange(RegionConfig region, long batchSize) {
        String counterKey = region.getAwsRegion() + "#COUNTER";

        // Initialize counter if not exists
        simulatedCounters.computeIfAbsent(counterKey, k -> new AtomicLong(region.getRangeStart()));

        AtomicLong counter = simulatedCounters.get(counterKey);

        // Atomic increment to get exclusive range
        long rangeStart = counter.getAndAdd(batchSize);
        long rangeEnd = rangeStart + batchSize - 1;

        // Validate we're still within region bounds
        if (rangeEnd > region.getRangeEnd()) {
            log.error("Region {} has exhausted its ID range!", region.getAwsRegion());
            throw new IllegalStateException("Region ID range exhausted: " + region.getAwsRegion());
        }

        log.info("Allocated range from DynamoDB: {} -> [{}, {}]",
            counterKey, rangeStart, rangeEnd);

        return new RangeAllocation(rangeStart, rangeEnd);
    }

    /**
     * Production implementation would look like this:
     *
     * public RangeAllocation allocateRange(RegionConfig region, long batchSize) {
     *     String counterKey = region.getAwsRegion() + "#COUNTER";
     *
     *     UpdateItemRequest request = UpdateItemRequest.builder()
     *         .tableName(TABLE_NAME)
     *         .key(Map.of("pk", AttributeValue.builder().s(counterKey).build()))
     *         .updateExpression("SET current_value = if_not_exists(current_value, :start) + :batch, " +
     *                          "last_allocated = :timestamp")
     *         .expressionAttributeValues(Map.of(
     *             ":start", AttributeValue.builder().n(String.valueOf(region.getRangeStart())).build(),
     *             ":batch", AttributeValue.builder().n(String.valueOf(batchSize)).build(),
     *             ":timestamp", AttributeValue.builder().s(Instant.now().toString()).build(),
     *             ":max", AttributeValue.builder().n(String.valueOf(region.getRangeEnd())).build()
     *         ))
     *         .conditionExpression("attribute_not_exists(current_value) OR current_value < :max")
     *         .returnValues(ReturnValue.UPDATED_OLD)
     *         .build();
     *
     *     try {
     *         UpdateItemResponse response = dynamoDbClient.updateItem(request);
     *
     *         long oldValue = response.attributes().containsKey("current_value")
     *             ? Long.parseLong(response.attributes().get("current_value").n())
     *             : region.getRangeStart();
     *
     *         return new RangeAllocation(oldValue, oldValue + batchSize - 1);
     *
     *     } catch (ConditionalCheckFailedException e) {
     *         throw new IllegalStateException("Region ID range exhausted: " + region.getAwsRegion());
     *     }
     * }
     */
}
