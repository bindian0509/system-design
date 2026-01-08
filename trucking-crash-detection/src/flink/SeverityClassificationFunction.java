package com.crashguard.flink;

import org.apache.flink.api.common.state.ValueState;
import org.apache.flink.api.common.state.ValueStateDescriptor;
import org.apache.flink.configuration.Configuration;
import org.apache.flink.streaming.api.functions.KeyedProcessFunction;
import org.apache.flink.util.Collector;
import org.apache.flink.util.OutputTag;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.*;

/**
 * Severity classification using ML model with circuit breaker fallback.
 *
 * This function:
 * 1. Calls ML inference service for severity classification
 * 2. Falls back to rule-based classification if ML is unavailable
 * 3. Implements circuit breaker pattern for resilience
 * 4. Tracks metrics for observability
 */
public class SeverityClassificationFunction
    extends KeyedProcessFunction<String, EnrichedCrashEvent, EnrichedCrashEvent> {

    // ============================================
    // CONFIGURATION
    // ============================================

    private static final String ML_SERVICE_URL =
        System.getenv().getOrDefault("ML_SERVICE_URL", "http://triton:8000/v2/models/severity/infer");

    private static final long ML_TIMEOUT_MS = 100;  // 100ms timeout for ML call
    private static final int CIRCUIT_BREAKER_THRESHOLD = 5;  // Failures before opening
    private static final long CIRCUIT_BREAKER_RESET_MS = 30_000;  // 30 seconds

    // Side output for events requiring manual review
    public static final OutputTag<CrashEvent> REVIEW_REQUIRED =
        new OutputTag<CrashEvent>("review-required") {};

    // ============================================
    // STATE
    // ============================================

    // Circuit breaker state
    private transient ValueState<CircuitBreakerState> circuitBreaker;

    // Metrics
    private transient ValueState<ClassificationMetrics> metrics;

    // Thread pool for async ML calls
    private transient ExecutorService executorService;

    @Override
    public void open(Configuration parameters) throws Exception {
        // Circuit breaker state
        ValueStateDescriptor<CircuitBreakerState> cbDescriptor =
            new ValueStateDescriptor<>("circuitBreaker", CircuitBreakerState.class);
        circuitBreaker = getRuntimeContext().getState(cbDescriptor);

        // Metrics state
        ValueStateDescriptor<ClassificationMetrics> metricsDescriptor =
            new ValueStateDescriptor<>("classificationMetrics", ClassificationMetrics.class);
        metrics = getRuntimeContext().getState(metricsDescriptor);

        // Executor for async calls
        executorService = Executors.newFixedThreadPool(4);
    }

    @Override
    public void close() throws Exception {
        if (executorService != null) {
            executorService.shutdown();
            executorService.awaitTermination(5, TimeUnit.SECONDS);
        }
    }

    @Override
    public void processElement(
            EnrichedCrashEvent event,
            Context ctx,
            Collector<EnrichedCrashEvent> out) throws Exception {

        long startTime = System.currentTimeMillis();
        ClassificationResult result;

        // ============================================
        // CHECK CIRCUIT BREAKER
        // ============================================
        CircuitBreakerState cbState = getCircuitBreakerState();

        if (cbState.isOpen()) {
            // Circuit is open - use fallback
            result = classifyWithRules(event);
            result.method = "rule_based_circuit_open";

            // Check if we should try half-open
            if (cbState.shouldAttemptReset()) {
                cbState.halfOpen();
                updateCircuitBreaker(cbState);
            }
        } else {
            // Circuit is closed or half-open - try ML
            try {
                result = classifyWithML(event);
                result.method = "ml_model";

                // Success - reset circuit breaker
                if (cbState.isHalfOpen()) {
                    cbState.close();
                    updateCircuitBreaker(cbState);
                }
            } catch (Exception e) {
                // ML failed - use fallback and update circuit breaker
                result = classifyWithRules(event);
                result.method = "rule_based_ml_failed";

                cbState.recordFailure();
                updateCircuitBreaker(cbState);

                logMLFailure(event, e);
            }
        }

        // ============================================
        // UPDATE EVENT WITH CLASSIFICATION
        // ============================================
        event.setSeverity(result.severity);
        event.setInjuryLikely(result.injuryLikely);
        event.setTowRequired(result.towRequired);
        event.setClassificationMethod(result.method);
        event.setClassificationConfidence(result.confidence);

        // ============================================
        // UPDATE METRICS
        // ============================================
        updateMetrics(result, System.currentTimeMillis() - startTime);

        // ============================================
        // OUTPUT
        // ============================================
        out.collect(event);

        // Send to review queue if uncertain
        if (result.confidence < 0.7 && event.getSeverity() >= 3) {
            ctx.output(REVIEW_REQUIRED, event.toCrashEvent());
        }
    }

    /**
     * Classify using ML model
     */
    private ClassificationResult classifyWithML(EnrichedCrashEvent event)
            throws Exception {

        Future<ClassificationResult> future = executorService.submit(() -> {
            return callMLService(event);
        });

        try {
            return future.get(ML_TIMEOUT_MS, TimeUnit.MILLISECONDS);
        } catch (TimeoutException e) {
            future.cancel(true);
            throw new MLTimeoutException("ML inference timed out after " + ML_TIMEOUT_MS + "ms");
        }
    }

    /**
     * Call ML inference service
     */
    private ClassificationResult callMLService(EnrichedCrashEvent event)
            throws Exception {

        URL url = new URL(ML_SERVICE_URL);
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();

        try {
            conn.setRequestMethod("POST");
            conn.setRequestProperty("Content-Type", "application/json");
            conn.setDoOutput(true);
            conn.setConnectTimeout((int) ML_TIMEOUT_MS);
            conn.setReadTimeout((int) ML_TIMEOUT_MS);

            // Build request payload
            String payload = buildMLRequest(event);

            try (OutputStream os = conn.getOutputStream()) {
                os.write(payload.getBytes(StandardCharsets.UTF_8));
            }

            int responseCode = conn.getResponseCode();
            if (responseCode != 200) {
                throw new MLServiceException("ML service returned " + responseCode);
            }

            // Parse response
            try (BufferedReader reader = new BufferedReader(
                    new InputStreamReader(conn.getInputStream()))) {
                StringBuilder response = new StringBuilder();
                String line;
                while ((line = reader.readLine()) != null) {
                    response.append(line);
                }
                return parseMLResponse(response.toString());
            }
        } finally {
            conn.disconnect();
        }
    }

    /**
     * Build ML inference request
     */
    private String buildMLRequest(EnrichedCrashEvent event) {
        // Triton Inference Server format
        return String.format("""
            {
                "inputs": [{
                    "name": "input",
                    "shape": [1, 10],
                    "datatype": "FP32",
                    "data": [%f, %f, %f, %f, %f, %f, %f, %f, %f, %f]
                }]
            }
            """,
            event.getMaxGForce(),
            event.getMaxRollRate(),
            event.getSpeedAtImpact(),
            event.getDeltaV(),
            event.getConfidence(),
            crashTypeToNumeric(event.getCrashType()),
            event.getVehicleWeight(),
            weatherToNumeric(event.getWeatherCondition()),
            roadTypeToNumeric(event.getRoadType()),
            event.getEventCount() * 1.0
        );
    }

    /**
     * Parse ML inference response
     */
    private ClassificationResult parseMLResponse(String response) {
        // Simplified parsing - in production use proper JSON library
        ClassificationResult result = new ClassificationResult();

        // Extract values from Triton response
        // Format: {"outputs":[{"data":[severity, injuryProb, towProb, confidence]}]}
        try {
            int dataStart = response.indexOf("\"data\":[") + 8;
            int dataEnd = response.indexOf("]", dataStart);
            String[] values = response.substring(dataStart, dataEnd).split(",");

            result.severity = (int) Math.round(Double.parseDouble(values[0].trim()));
            result.injuryLikely = Double.parseDouble(values[1].trim()) > 0.5;
            result.towRequired = Double.parseDouble(values[2].trim()) > 0.5;
            result.confidence = Double.parseDouble(values[3].trim());

            // Clamp severity to valid range
            result.severity = Math.max(1, Math.min(5, result.severity));

        } catch (Exception e) {
            // Parsing failed - use defaults
            result.severity = 3;
            result.confidence = 0.5;
        }

        return result;
    }

    /**
     * Rule-based fallback classification
     */
    private ClassificationResult classifyWithRules(EnrichedCrashEvent event) {
        ClassificationResult result = new ClassificationResult();

        double gForce = event.getMaxGForce();
        double speed = event.getSpeedAtImpact();
        CrashType type = event.getCrashType();

        // Severity based on G-force and speed
        if (gForce >= 15 || (gForce >= 10 && speed >= 25)) {
            result.severity = 5;  // Catastrophic
            result.injuryLikely = true;
            result.towRequired = true;
            result.confidence = 0.9;
        } else if (gForce >= 10 || (gForce >= 6 && speed >= 20)) {
            result.severity = 4;  // Severe
            result.injuryLikely = true;
            result.towRequired = true;
            result.confidence = 0.85;
        } else if (gForce >= 6 || (gForce >= 4 && speed >= 15)) {
            result.severity = 3;  // Moderate
            result.injuryLikely = speed > 20;
            result.towRequired = gForce >= 5;
            result.confidence = 0.75;
        } else if (gForce >= 4) {
            result.severity = 2;  // Minor
            result.injuryLikely = false;
            result.towRequired = false;
            result.confidence = 0.7;
        } else {
            result.severity = 1;  // Minimal
            result.injuryLikely = false;
            result.towRequired = false;
            result.confidence = 0.65;
        }

        // Adjust for rollover (always serious)
        if (type == CrashType.ROLLOVER) {
            result.severity = Math.max(result.severity, 4);
            result.injuryLikely = true;
            result.towRequired = true;
        }

        return result;
    }

    // ============================================
    // CIRCUIT BREAKER METHODS
    // ============================================

    private CircuitBreakerState getCircuitBreakerState() throws Exception {
        CircuitBreakerState state = circuitBreaker.value();
        if (state == null) {
            state = new CircuitBreakerState();
        }
        return state;
    }

    private void updateCircuitBreaker(CircuitBreakerState state) throws Exception {
        circuitBreaker.update(state);
    }

    // ============================================
    // HELPER METHODS
    // ============================================

    private double crashTypeToNumeric(CrashType type) {
        return switch (type) {
            case FRONTAL -> 1.0;
            case REAR -> 2.0;
            case SIDE_LEFT -> 3.0;
            case SIDE_RIGHT -> 4.0;
            case ROLLOVER -> 5.0;
            default -> 0.0;
        };
    }

    private double weatherToNumeric(String weather) {
        if (weather == null) return 0.0;
        return switch (weather.toLowerCase()) {
            case "clear" -> 1.0;
            case "rain" -> 2.0;
            case "snow" -> 3.0;
            case "fog" -> 4.0;
            case "ice" -> 5.0;
            default -> 0.0;
        };
    }

    private double roadTypeToNumeric(String roadType) {
        if (roadType == null) return 0.0;
        return switch (roadType.toLowerCase()) {
            case "highway" -> 1.0;
            case "urban" -> 2.0;
            case "rural" -> 3.0;
            case "residential" -> 4.0;
            default -> 0.0;
        };
    }

    private void updateMetrics(ClassificationResult result, long latencyMs)
            throws Exception {
        ClassificationMetrics m = metrics.value();
        if (m == null) {
            m = new ClassificationMetrics();
        }

        m.totalClassifications++;
        m.totalLatencyMs += latencyMs;

        if (result.method.startsWith("ml_")) {
            m.mlClassifications++;
        } else {
            m.fallbackClassifications++;
        }

        metrics.update(m);
    }

    private void logMLFailure(EnrichedCrashEvent event, Exception e) {
        System.err.printf(
            "[ML_FAILURE] vehicle=%s error=%s using_fallback=true%n",
            event.getVehicleId(),
            e.getMessage()
        );
    }

    // ============================================
    // INNER CLASSES
    // ============================================

    private static class ClassificationResult {
        int severity;
        boolean injuryLikely;
        boolean towRequired;
        double confidence;
        String method;
    }

    private static class CircuitBreakerState implements java.io.Serializable {
        private static final long serialVersionUID = 1L;

        enum State { CLOSED, OPEN, HALF_OPEN }

        State state = State.CLOSED;
        int failureCount = 0;
        long lastFailureTime = 0;
        long openedAt = 0;

        boolean isOpen() { return state == State.OPEN; }
        boolean isHalfOpen() { return state == State.HALF_OPEN; }

        void recordFailure() {
            failureCount++;
            lastFailureTime = System.currentTimeMillis();

            if (failureCount >= CIRCUIT_BREAKER_THRESHOLD) {
                state = State.OPEN;
                openedAt = System.currentTimeMillis();
            }
        }

        boolean shouldAttemptReset() {
            return state == State.OPEN &&
                   (System.currentTimeMillis() - openedAt) >= CIRCUIT_BREAKER_RESET_MS;
        }

        void halfOpen() {
            state = State.HALF_OPEN;
        }

        void close() {
            state = State.CLOSED;
            failureCount = 0;
        }
    }

    private static class ClassificationMetrics implements java.io.Serializable {
        private static final long serialVersionUID = 1L;

        long totalClassifications;
        long mlClassifications;
        long fallbackClassifications;
        long totalLatencyMs;
    }

    private static class MLTimeoutException extends Exception {
        MLTimeoutException(String message) { super(message); }
    }

    private static class MLServiceException extends Exception {
        MLServiceException(String message) { super(message); }
    }
}

