package com.crashguard.flink;

import org.apache.flink.api.common.state.ValueState;
import org.apache.flink.api.common.state.ValueStateDescriptor;
import org.apache.flink.configuration.Configuration;
import org.apache.flink.streaming.api.functions.windowing.ProcessWindowFunction;
import org.apache.flink.streaming.api.windowing.windows.TimeWindow;
import org.apache.flink.util.Collector;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.UUID;
import java.util.stream.Collectors;
import java.util.stream.StreamSupport;

/**
 * Window function for crash detection using multi-signal fusion.
 *
 * This function processes telemetry events in 100ms tumbling windows
 * and applies crash detection algorithms based on:
 * - Accelerometer data (G-force)
 * - Gyroscope data (angular velocity)
 * - Speed changes
 * - GPS context
 */
public class CrashDetectionWindowFunction
    extends ProcessWindowFunction<TelemetryEvent, CrashEvent, String, TimeWindow> {

    // ============================================
    // CRASH DETECTION THRESHOLDS
    // ============================================

    // G-Force thresholds (based on NHTSA crash pulse data)
    private static final double G_FORCE_DEFINITE = 15.0;    // Definite severe crash
    private static final double G_FORCE_PROBABLE = 8.0;     // Probable crash
    private static final double G_FORCE_POSSIBLE = 4.0;     // Possible crash
    private static final double G_FORCE_HARD_BRAKE = 0.7;   // Hard braking (not crash)

    // Gyroscope thresholds (degrees per second)
    private static final double ROLL_RATE_ROLLOVER = 90.0;  // Potential rollover
    private static final double YAW_RATE_SPINOUT = 120.0;   // Potential spin-out

    // Speed change thresholds
    private static final double SPEED_DROP_THRESHOLD_MPS = 8.9;  // ~20 mph in 0.5s

    // Signal weights for fusion
    private static final double WEIGHT_G_FORCE = 0.40;
    private static final double WEIGHT_GYROSCOPE = 0.25;
    private static final double WEIGHT_SPEED = 0.20;
    private static final double WEIGHT_GPS = 0.15;

    // State for tracking recent crashes (deduplication)
    private transient ValueState<Long> lastCrashTimestamp;

    // State for vehicle baseline (normal driving patterns)
    private transient ValueState<VehicleBaseline> vehicleBaseline;

    @Override
    public void open(Configuration parameters) throws Exception {
        // State for crash deduplication
        ValueStateDescriptor<Long> crashTimestampDescriptor =
            new ValueStateDescriptor<>("lastCrashTimestamp", Long.class);
        lastCrashTimestamp = getRuntimeContext().getState(crashTimestampDescriptor);

        // State for vehicle baseline patterns
        ValueStateDescriptor<VehicleBaseline> baselineDescriptor =
            new ValueStateDescriptor<>("vehicleBaseline", VehicleBaseline.class);
        vehicleBaseline = getRuntimeContext().getState(baselineDescriptor);
    }

    @Override
    public void process(
            String vehicleId,
            Context context,
            Iterable<TelemetryEvent> events,
            Collector<CrashEvent> out) throws Exception {

        // Convert to sorted list
        List<TelemetryEvent> eventList = StreamSupport
            .stream(events.spliterator(), false)
            .sorted(Comparator.comparingLong(TelemetryEvent::getEventTime))
            .collect(Collectors.toList());

        if (eventList.isEmpty()) {
            return;
        }

        // ============================================
        // DEDUPLICATION CHECK
        // ============================================
        Long lastCrash = lastCrashTimestamp.value();
        long windowEnd = context.window().getEnd();

        // Don't report crashes within 5 seconds of a previous one
        if (lastCrash != null && (windowEnd - lastCrash) < 5000) {
            return;
        }

        // ============================================
        // EXTRACT SIGNALS
        // ============================================
        SignalAnalysis analysis = analyzeSignals(eventList);

        // ============================================
        // CALCULATE CONFIDENCE SCORE (Signal Fusion)
        // ============================================
        double gForceScore = scoreGForce(analysis.maxGForce);
        double gyroScore = scoreGyroscope(analysis.maxRollRate, analysis.maxYawRate);
        double speedScore = scoreSpeedChange(analysis.speedDrop, analysis.initialSpeed);
        double gpsScore = scoreGpsContext(analysis.stoppedAfterMoving, analysis.pathDeviation);

        double confidence =
            (WEIGHT_G_FORCE * gForceScore) +
            (WEIGHT_GYROSCOPE * gyroScore) +
            (WEIGHT_SPEED * speedScore) +
            (WEIGHT_GPS * gpsScore);

        // ============================================
        // DECISION AND OUTPUT
        // ============================================
        if (confidence > 0.40) {
            CrashType crashType = determineCrashType(analysis);
            int severity = determineSeverity(analysis, confidence);

            TelemetryEvent lastEvent = eventList.get(eventList.size() - 1);

            CrashEvent crashEvent = CrashEvent.builder()
                .eventId(UUID.randomUUID().toString())
                .vehicleId(vehicleId)
                .detectedAt(System.currentTimeMillis())
                .eventTime(lastEvent.getEventTime())
                .confidence(confidence)
                .crashType(crashType)
                .severity(severity)
                .maxGForce(analysis.maxGForce)
                .maxRollRate(analysis.maxRollRate)
                .speedAtImpact(analysis.speedAtImpact)
                .latitude(lastEvent.getLatitude())
                .longitude(lastEvent.getLongitude())
                .windowStart(context.window().getStart())
                .windowEnd(context.window().getEnd())
                .eventCount(eventList.size())
                .signalScores(new SignalScores(gForceScore, gyroScore, speedScore, gpsScore))
                .build();

            // Update last crash timestamp for deduplication
            lastCrashTimestamp.update(windowEnd);

            // Emit the crash event
            out.collect(crashEvent);

            // Log for observability
            logCrashDetection(crashEvent, analysis);
        }

        // ============================================
        // UPDATE BASELINE (for anomaly detection)
        // ============================================
        updateBaseline(analysis);
    }

    /**
     * Analyze all signals from the telemetry events
     */
    private SignalAnalysis analyzeSignals(List<TelemetryEvent> events) {
        SignalAnalysis analysis = new SignalAnalysis();

        double maxGForce = 0;
        double maxRollRate = 0;
        double maxYawRate = 0;
        double initialSpeed = events.get(0).getSpeedMps();
        double finalSpeed = events.get(events.size() - 1).getSpeedMps();
        double speedAtMaxG = 0;

        double sumAccelX = 0, sumAccelY = 0, sumAccelZ = 0;
        int count = 0;

        for (TelemetryEvent event : events) {
            // Calculate G-force magnitude
            double gForce = calculateGForceMagnitude(
                event.getAccelX(),
                event.getAccelY(),
                event.getAccelZ()
            );

            if (gForce > maxGForce) {
                maxGForce = gForce;
                speedAtMaxG = event.getSpeedMps();
            }

            // Track angular rates
            maxRollRate = Math.max(maxRollRate, Math.abs(event.getGyroRoll()));
            maxYawRate = Math.max(maxYawRate, Math.abs(event.getGyroYaw()));

            // Sum for direction analysis
            sumAccelX += event.getAccelX();
            sumAccelY += event.getAccelY();
            sumAccelZ += event.getAccelZ();
            count++;
        }

        analysis.maxGForce = maxGForce;
        analysis.maxRollRate = maxRollRate;
        analysis.maxYawRate = maxYawRate;
        analysis.initialSpeed = initialSpeed;
        analysis.finalSpeed = finalSpeed;
        analysis.speedDrop = initialSpeed - finalSpeed;
        analysis.speedAtImpact = speedAtMaxG;
        analysis.stoppedAfterMoving = (initialSpeed > 5 && finalSpeed < 1);

        // Determine primary force direction
        analysis.avgAccelX = sumAccelX / count;
        analysis.avgAccelY = sumAccelY / count;
        analysis.avgAccelZ = sumAccelZ / count;

        // Calculate path deviation (simplified)
        analysis.pathDeviation = calculatePathDeviation(events);

        return analysis;
    }

    /**
     * Calculate G-force magnitude from 3-axis accelerometer
     */
    private double calculateGForceMagnitude(double x, double y, double z) {
        // Subtract 1g for gravity on Z-axis (assuming vehicle is level)
        double adjustedZ = z - 1.0;
        return Math.sqrt(x * x + y * y + adjustedZ * adjustedZ);
    }

    /**
     * Score G-force signal (0.0 to 1.0)
     */
    private double scoreGForce(double gForce) {
        if (gForce >= G_FORCE_DEFINITE) return 1.0;
        if (gForce >= G_FORCE_PROBABLE) return 0.8;
        if (gForce >= G_FORCE_POSSIBLE) return 0.5;
        if (gForce >= G_FORCE_HARD_BRAKE) return 0.2;
        return 0.0;
    }

    /**
     * Score gyroscope signals (0.0 to 1.0)
     */
    private double scoreGyroscope(double rollRate, double yawRate) {
        double rollScore = 0;
        double yawScore = 0;

        if (rollRate >= ROLL_RATE_ROLLOVER) {
            rollScore = 0.9;
        } else if (rollRate >= 45) {
            rollScore = 0.5;
        }

        if (yawRate >= YAW_RATE_SPINOUT) {
            yawScore = 0.8;
        } else if (yawRate >= 60) {
            yawScore = 0.4;
        }

        return Math.max(rollScore, yawScore);
    }

    /**
     * Score speed change signal (0.0 to 1.0)
     */
    private double scoreSpeedChange(double speedDrop, double initialSpeed) {
        if (initialSpeed < 5) {
            return 0.0; // Vehicle was barely moving
        }

        // Sudden stop from high speed
        if (speedDrop >= 13.4 && initialSpeed >= 22.3) { // 30mph drop from 50mph+
            return 0.9;
        }

        // Significant deceleration
        if (speedDrop >= SPEED_DROP_THRESHOLD_MPS) {
            return 0.7;
        }

        // Moderate deceleration
        if (speedDrop >= 4.5) { // ~10mph
            return 0.3;
        }

        return 0.0;
    }

    /**
     * Score GPS context (0.0 to 1.0)
     */
    private double scoreGpsContext(boolean stoppedAfterMoving, double pathDeviation) {
        double score = 0;

        if (stoppedAfterMoving) {
            score += 0.5;
        }

        // Path deviation indicates loss of control
        if (pathDeviation > 10) { // > 10 meters off expected path
            score += 0.3;
        }

        return Math.min(1.0, score);
    }

    /**
     * Determine crash type based on signal analysis
     */
    private CrashType determineCrashType(SignalAnalysis analysis) {
        // Rollover: High roll rate with Z-axis acceleration
        if (analysis.maxRollRate >= ROLL_RATE_ROLLOVER &&
            Math.abs(analysis.avgAccelZ - 1.0) > 0.5) {
            return CrashType.ROLLOVER;
        }

        // Frontal: High negative X acceleration
        if (analysis.avgAccelX < -3) {
            return CrashType.FRONTAL;
        }

        // Rear: High positive X acceleration
        if (analysis.avgAccelX > 3) {
            return CrashType.REAR;
        }

        // Side: High Y acceleration
        if (Math.abs(analysis.avgAccelY) > 3) {
            return analysis.avgAccelY > 0 ? CrashType.SIDE_RIGHT : CrashType.SIDE_LEFT;
        }

        return CrashType.UNKNOWN;
    }

    /**
     * Determine crash severity (1-5)
     */
    private int determineSeverity(SignalAnalysis analysis, double confidence) {
        // Severity based on G-force and confidence
        if (analysis.maxGForce >= 15 && confidence >= 0.9) {
            return 5; // Catastrophic
        }
        if (analysis.maxGForce >= 10 || confidence >= 0.85) {
            return 4; // Severe
        }
        if (analysis.maxGForce >= 6 || confidence >= 0.75) {
            return 3; // Moderate
        }
        if (analysis.maxGForce >= 4 || confidence >= 0.65) {
            return 2; // Minor
        }
        return 1; // Minimal
    }

    /**
     * Calculate path deviation from expected trajectory
     */
    private double calculatePathDeviation(List<TelemetryEvent> events) {
        if (events.size() < 2) return 0;

        // Simplified: calculate maximum deviation from straight line
        TelemetryEvent first = events.get(0);
        TelemetryEvent last = events.get(events.size() - 1);

        double maxDeviation = 0;
        for (TelemetryEvent event : events) {
            double deviation = pointToLineDistance(
                event.getLatitude(), event.getLongitude(),
                first.getLatitude(), first.getLongitude(),
                last.getLatitude(), last.getLongitude()
            );
            maxDeviation = Math.max(maxDeviation, deviation);
        }

        return maxDeviation;
    }

    /**
     * Calculate distance from point to line (in meters, simplified)
     */
    private double pointToLineDistance(
            double px, double py,
            double x1, double y1,
            double x2, double y2) {
        // Simplified calculation - should use proper geodesic for production
        double dx = x2 - x1;
        double dy = y2 - y1;
        double length = Math.sqrt(dx * dx + dy * dy);

        if (length == 0) return 0;

        double t = ((px - x1) * dx + (py - y1) * dy) / (length * length);
        t = Math.max(0, Math.min(1, t));

        double nearestX = x1 + t * dx;
        double nearestY = y1 + t * dy;

        // Convert to meters (approximate)
        double latDiff = (px - nearestX) * 111320;
        double lonDiff = (py - nearestY) * 111320 * Math.cos(Math.toRadians(px));

        return Math.sqrt(latDiff * latDiff + lonDiff * lonDiff);
    }

    /**
     * Update vehicle baseline for anomaly detection
     */
    private void updateBaseline(SignalAnalysis analysis) throws Exception {
        VehicleBaseline baseline = vehicleBaseline.value();
        if (baseline == null) {
            baseline = new VehicleBaseline();
        }

        // Exponential moving average of normal driving patterns
        baseline.updateWithNewData(analysis);
        vehicleBaseline.update(baseline);
    }

    /**
     * Log crash detection for observability
     */
    private void logCrashDetection(CrashEvent event, SignalAnalysis analysis) {
        // In production, this would use structured logging (e.g., SLF4J with JSON)
        System.out.printf(
            "[CRASH_DETECTED] vehicle=%s confidence=%.3f type=%s severity=%d " +
            "g_force=%.2f roll_rate=%.2f speed_at_impact=%.2f%n",
            event.getVehicleId(),
            event.getConfidence(),
            event.getCrashType(),
            event.getSeverity(),
            event.getMaxGForce(),
            analysis.maxRollRate,
            event.getSpeedAtImpact()
        );
    }

    // ============================================
    // INNER CLASSES
    // ============================================

    /**
     * Analysis results from signal processing
     */
    private static class SignalAnalysis {
        double maxGForce;
        double maxRollRate;
        double maxYawRate;
        double initialSpeed;
        double finalSpeed;
        double speedDrop;
        double speedAtImpact;
        boolean stoppedAfterMoving;
        double avgAccelX;
        double avgAccelY;
        double avgAccelZ;
        double pathDeviation;
    }
}

