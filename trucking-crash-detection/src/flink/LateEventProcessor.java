package com.crashguard.flink;

import org.apache.flink.api.common.state.ListState;
import org.apache.flink.api.common.state.ListStateDescriptor;
import org.apache.flink.api.common.state.ValueState;
import org.apache.flink.api.common.state.ValueStateDescriptor;
import org.apache.flink.api.common.typeinfo.TypeHint;
import org.apache.flink.api.common.typeinfo.TypeInformation;
import org.apache.flink.configuration.Configuration;
import org.apache.flink.streaming.api.functions.KeyedProcessFunction;
import org.apache.flink.util.Collector;

import java.util.*;
import java.util.stream.Collectors;

/**
 * Processor for late-arriving telemetry events.
 *
 * This handles scenarios where:
 * 1. Network connectivity was lost and data arrives in a burst after recovery
 * 2. Provider API was down and we receive historical data on reconnection
 * 3. Events arrive significantly out-of-order due to queuing
 *
 * Strategy:
 * - Buffer late events for a vehicle until we have enough data
 * - Analyze buffered events for potential missed crashes
 * - Emit with special flags for downstream awareness
 * - Avoid duplicate alerts if crash was already detected via on-time events
 */
public class LateEventProcessor
    extends KeyedProcessFunction<String, TelemetryEvent, CrashEvent> {

    // ============================================
    // CONFIGURATION
    // ============================================

    // How long to buffer late events before processing
    private static final long BUFFER_TIMEOUT_MS = 10_000; // 10 seconds

    // Minimum events needed to analyze for crash
    private static final int MIN_EVENTS_FOR_ANALYSIS = 5;

    // Maximum events to buffer per vehicle
    private static final int MAX_BUFFER_SIZE = 1000;

    // How long to remember processed crash events (for dedup)
    private static final long CRASH_MEMORY_MS = 60_000; // 1 minute

    // ============================================
    // STATE
    // ============================================

    // Buffer for late-arriving events
    private transient ListState<TelemetryEvent> eventBuffer;

    // Timer for triggering buffer processing
    private transient ValueState<Long> bufferTimerTimestamp;

    // Previously detected crashes (for deduplication)
    private transient ListState<CrashRecord> recentCrashes;

    // Metrics
    private transient ValueState<LateEventMetrics> metrics;

    @Override
    public void open(Configuration parameters) throws Exception {
        // Event buffer state
        ListStateDescriptor<TelemetryEvent> bufferDescriptor =
            new ListStateDescriptor<>("lateEventBuffer", TelemetryEvent.class);
        eventBuffer = getRuntimeContext().getListState(bufferDescriptor);

        // Timer state
        ValueStateDescriptor<Long> timerDescriptor =
            new ValueStateDescriptor<>("bufferTimer", Long.class);
        bufferTimerTimestamp = getRuntimeContext().getState(timerDescriptor);

        // Recent crashes for dedup
        ListStateDescriptor<CrashRecord> crashDescriptor =
            new ListStateDescriptor<>("recentCrashes", CrashRecord.class);
        recentCrashes = getRuntimeContext().getListState(crashDescriptor);

        // Metrics state
        ValueStateDescriptor<LateEventMetrics> metricsDescriptor =
            new ValueStateDescriptor<>("lateEventMetrics", LateEventMetrics.class);
        metrics = getRuntimeContext().getState(metricsDescriptor);
    }

    @Override
    public void processElement(
            TelemetryEvent event,
            Context ctx,
            Collector<CrashEvent> out) throws Exception {

        String vehicleId = event.getVehicleId();
        long currentProcessingTime = ctx.timerService().currentProcessingTime();

        // ============================================
        // UPDATE METRICS
        // ============================================
        updateMetrics(event, currentProcessingTime);

        // ============================================
        // ADD TO BUFFER
        // ============================================
        addToBuffer(event);

        // ============================================
        // SET/UPDATE TIMER FOR BUFFER PROCESSING
        // ============================================
        Long currentTimer = bufferTimerTimestamp.value();
        if (currentTimer == null) {
            // No timer set, create one
            long timerTime = currentProcessingTime + BUFFER_TIMEOUT_MS;
            ctx.timerService().registerProcessingTimeTimer(timerTime);
            bufferTimerTimestamp.update(timerTime);
        }

        // ============================================
        // IMMEDIATE PROCESSING FOR HIGH-SEVERITY SIGNALS
        // ============================================
        if (isHighSeveritySignal(event)) {
            // Process immediately without waiting for buffer timeout
            processBufferedEvents(ctx, out, true);
        }
    }

    @Override
    public void onTimer(
            long timestamp,
            OnTimerContext ctx,
            Collector<CrashEvent> out) throws Exception {

        // Timer fired - process buffered events
        processBufferedEvents(ctx, out, false);

        // Clear timer state
        bufferTimerTimestamp.clear();
    }

    /**
     * Add event to buffer with size limit
     */
    private void addToBuffer(TelemetryEvent event) throws Exception {
        List<TelemetryEvent> currentBuffer = new ArrayList<>();
        for (TelemetryEvent e : eventBuffer.get()) {
            currentBuffer.add(e);
        }

        // Size limit check
        if (currentBuffer.size() >= MAX_BUFFER_SIZE) {
            // Remove oldest events
            currentBuffer.sort(Comparator.comparingLong(TelemetryEvent::getEventTime));
            currentBuffer = currentBuffer.subList(
                currentBuffer.size() - MAX_BUFFER_SIZE + 1,
                currentBuffer.size()
            );
        }

        currentBuffer.add(event);
        eventBuffer.update(currentBuffer);
    }

    /**
     * Process buffered late events
     */
    private void processBufferedEvents(
            KeyedProcessFunction<String, TelemetryEvent, CrashEvent>.Context ctx,
            Collector<CrashEvent> out,
            boolean isImmediateProcessing) throws Exception {

        List<TelemetryEvent> events = new ArrayList<>();
        for (TelemetryEvent e : eventBuffer.get()) {
            events.add(e);
        }

        if (events.size() < MIN_EVENTS_FOR_ANALYSIS) {
            return;
        }

        // Sort by event time
        events.sort(Comparator.comparingLong(TelemetryEvent::getEventTime));

        // ============================================
        // FIND POTENTIAL CRASH WINDOWS
        // ============================================
        List<CrashCandidate> candidates = findCrashCandidates(events);

        for (CrashCandidate candidate : candidates) {
            // Check for duplicates
            if (isDuplicateCrash(candidate)) {
                continue;
            }

            // Create crash event
            CrashEvent crashEvent = CrashEvent.builder()
                .eventId(UUID.randomUUID().toString())
                .vehicleId(ctx.getCurrentKey())
                .detectedAt(System.currentTimeMillis())
                .eventTime(candidate.eventTime)
                .confidence(candidate.confidence)
                .crashType(candidate.crashType)
                .severity(candidate.severity)
                .maxGForce(candidate.maxGForce)
                .latitude(candidate.latitude)
                .longitude(candidate.longitude)
                .isLateDetection(true)  // Flag this as late detection
                .latenessDurationMs(System.currentTimeMillis() - candidate.eventTime)
                .eventCount(candidate.eventCount)
                .build();

            // Record for dedup
            recordCrash(crashEvent);

            // Emit
            out.collect(crashEvent);

            // Log
            logLateDetection(crashEvent, isImmediateProcessing);
        }

        // ============================================
        // CLEANUP OLD EVENTS FROM BUFFER
        // ============================================
        cleanupBuffer(events);

        // ============================================
        // CLEANUP OLD CRASH RECORDS
        // ============================================
        cleanupCrashRecords();
    }

    /**
     * Find crash candidates in a sequence of events
     */
    private List<CrashCandidate> findCrashCandidates(List<TelemetryEvent> events) {
        List<CrashCandidate> candidates = new ArrayList<>();

        // Sliding window analysis
        int windowSize = 10; // 10 events ≈ 100ms at 100Hz

        for (int i = 0; i <= events.size() - windowSize; i++) {
            List<TelemetryEvent> window = events.subList(i, i + windowSize);

            CrashCandidate candidate = analyzeWindow(window);
            if (candidate != null && candidate.confidence > 0.65) {
                candidates.add(candidate);
                // Skip ahead to avoid overlapping detections
                i += windowSize - 1;
            }
        }

        return candidates;
    }

    /**
     * Analyze a window of events for crash indicators
     */
    private CrashCandidate analyzeWindow(List<TelemetryEvent> events) {
        double maxGForce = 0;
        double maxRollRate = 0;
        TelemetryEvent maxGForceEvent = null;

        for (TelemetryEvent event : events) {
            double gForce = Math.sqrt(
                event.getAccelX() * event.getAccelX() +
                event.getAccelY() * event.getAccelY() +
                Math.pow(event.getAccelZ() - 1.0, 2)
            );

            if (gForce > maxGForce) {
                maxGForce = gForce;
                maxGForceEvent = event;
            }

            maxRollRate = Math.max(maxRollRate, Math.abs(event.getGyroRoll()));
        }

        // Calculate confidence (simplified version)
        double confidence = 0;

        if (maxGForce >= 15.0) confidence = 0.95;
        else if (maxGForce >= 8.0) confidence = 0.80;
        else if (maxGForce >= 4.0) confidence = 0.50;
        else return null;

        if (maxRollRate >= 90.0) {
            confidence = Math.max(confidence, 0.85);
        }

        if (confidence < 0.50) return null;

        CrashCandidate candidate = new CrashCandidate();
        candidate.eventTime = maxGForceEvent.getEventTime();
        candidate.confidence = confidence;
        candidate.maxGForce = maxGForce;
        candidate.latitude = maxGForceEvent.getLatitude();
        candidate.longitude = maxGForceEvent.getLongitude();
        candidate.eventCount = events.size();
        candidate.crashType = determineCrashType(events);
        candidate.severity = determineSeverity(maxGForce, confidence);

        return candidate;
    }

    /**
     * Check if this crash was already detected
     */
    private boolean isDuplicateCrash(CrashCandidate candidate) throws Exception {
        for (CrashRecord record : recentCrashes.get()) {
            // Same approximate time (within 5 seconds)
            if (Math.abs(record.eventTime - candidate.eventTime) < 5000) {
                return true;
            }
        }
        return false;
    }

    /**
     * Record crash for future dedup checks
     */
    private void recordCrash(CrashEvent event) throws Exception {
        List<CrashRecord> records = new ArrayList<>();
        for (CrashRecord r : recentCrashes.get()) {
            records.add(r);
        }

        CrashRecord newRecord = new CrashRecord();
        newRecord.eventId = event.getEventId();
        newRecord.eventTime = event.getEventTime();
        newRecord.detectedAt = event.getDetectedAt();

        records.add(newRecord);
        recentCrashes.update(records);
    }

    /**
     * Cleanup old events from buffer
     */
    private void cleanupBuffer(List<TelemetryEvent> events) throws Exception {
        // Keep only events from last 30 seconds
        long cutoff = System.currentTimeMillis() - 30_000;

        List<TelemetryEvent> recentEvents = events.stream()
            .filter(e -> e.getEventTime() > cutoff)
            .collect(Collectors.toList());

        eventBuffer.update(recentEvents);
    }

    /**
     * Cleanup old crash records
     */
    private void cleanupCrashRecords() throws Exception {
        long cutoff = System.currentTimeMillis() - CRASH_MEMORY_MS;

        List<CrashRecord> records = new ArrayList<>();
        for (CrashRecord r : recentCrashes.get()) {
            if (r.detectedAt > cutoff) {
                records.add(r);
            }
        }

        recentCrashes.update(records);
    }

    /**
     * Check if event has high-severity signals requiring immediate processing
     */
    private boolean isHighSeveritySignal(TelemetryEvent event) {
        double gForce = Math.sqrt(
            event.getAccelX() * event.getAccelX() +
            event.getAccelY() * event.getAccelY() +
            Math.pow(event.getAccelZ() - 1.0, 2)
        );

        return gForce >= 10.0 || Math.abs(event.getGyroRoll()) >= 90.0;
    }

    /**
     * Update metrics for observability
     */
    private void updateMetrics(TelemetryEvent event, long currentTime) throws Exception {
        LateEventMetrics m = metrics.value();
        if (m == null) {
            m = new LateEventMetrics();
        }

        long lateness = currentTime - event.getEventTime();
        m.totalLateEvents++;
        m.totalLatenessMs += lateness;
        m.maxLatenessMs = Math.max(m.maxLatenessMs, lateness);

        metrics.update(m);
    }

    /**
     * Log late detection for observability
     */
    private void logLateDetection(CrashEvent event, boolean isImmediate) {
        System.out.printf(
            "[LATE_CRASH_DETECTED] vehicle=%s confidence=%.3f lateness=%dms immediate=%s%n",
            event.getVehicleId(),
            event.getConfidence(),
            event.getLatenessDurationMs(),
            isImmediate
        );
    }

    private CrashType determineCrashType(List<TelemetryEvent> events) {
        // Simplified - use average acceleration direction
        double avgX = events.stream().mapToDouble(TelemetryEvent::getAccelX).average().orElse(0);
        double avgY = events.stream().mapToDouble(TelemetryEvent::getAccelY).average().orElse(0);

        if (avgX < -3) return CrashType.FRONTAL;
        if (avgX > 3) return CrashType.REAR;
        if (Math.abs(avgY) > 3) return avgY > 0 ? CrashType.SIDE_RIGHT : CrashType.SIDE_LEFT;
        return CrashType.UNKNOWN;
    }

    private int determineSeverity(double maxGForce, double confidence) {
        if (maxGForce >= 15) return 5;
        if (maxGForce >= 10) return 4;
        if (maxGForce >= 6) return 3;
        if (maxGForce >= 4) return 2;
        return 1;
    }

    // ============================================
    // INNER CLASSES
    // ============================================

    private static class CrashCandidate {
        long eventTime;
        double confidence;
        double maxGForce;
        double latitude;
        double longitude;
        int eventCount;
        CrashType crashType;
        int severity;
    }

    private static class CrashRecord {
        String eventId;
        long eventTime;
        long detectedAt;
    }

    private static class LateEventMetrics {
        long totalLateEvents;
        long totalLatenessMs;
        long maxLatenessMs;
    }
}


