package com.crashguard.flink.models;

import java.io.Serializable;

/**
 * Detected crash event.
 * Represents a crash detected from analyzing telemetry data.
 */
public class CrashEvent implements Serializable {

    private static final long serialVersionUID = 1L;

    // Identifiers
    private String eventId;
    private String vehicleId;
    private String policyId;

    // Timestamps
    private long detectedAt;       // When crash was detected (processing time)
    private long eventTime;        // When crash occurred (event time)

    // Detection info
    private double confidence;
    private CrashType crashType;
    private int severity;          // 1-5 scale

    // Crash metrics
    private double maxGForce;
    private double maxRollRate;
    private double speedAtImpact;
    private double deltaV;

    // Location
    private double latitude;
    private double longitude;
    private String address;

    // Window info
    private long windowStart;
    private long windowEnd;
    private int eventCount;

    // Signal scores (for debugging/analysis)
    private SignalScores signalScores;

    // Late detection flags
    private boolean isLateDetection;
    private long latenessDurationMs;

    // Model info
    private String modelVersion;
    private String detectionMethod;  // ml_model, rule_based, hybrid

    // Constructors
    public CrashEvent() {}

    // Builder pattern
    public static Builder builder() {
        return new Builder();
    }

    // Getters
    public String getEventId() { return eventId; }
    public String getVehicleId() { return vehicleId; }
    public String getPolicyId() { return policyId; }
    public long getDetectedAt() { return detectedAt; }
    public long getEventTime() { return eventTime; }
    public double getConfidence() { return confidence; }
    public CrashType getCrashType() { return crashType; }
    public int getSeverity() { return severity; }
    public double getMaxGForce() { return maxGForce; }
    public double getMaxRollRate() { return maxRollRate; }
    public double getSpeedAtImpact() { return speedAtImpact; }
    public double getDeltaV() { return deltaV; }
    public double getLatitude() { return latitude; }
    public double getLongitude() { return longitude; }
    public String getAddress() { return address; }
    public long getWindowStart() { return windowStart; }
    public long getWindowEnd() { return windowEnd; }
    public int getEventCount() { return eventCount; }
    public SignalScores getSignalScores() { return signalScores; }
    public boolean isLateDetection() { return isLateDetection; }
    public long getLatenessDurationMs() { return latenessDurationMs; }
    public String getModelVersion() { return modelVersion; }
    public String getDetectionMethod() { return detectionMethod; }

    public static class Builder {
        private final CrashEvent event = new CrashEvent();

        public Builder eventId(String val) { event.eventId = val; return this; }
        public Builder vehicleId(String val) { event.vehicleId = val; return this; }
        public Builder policyId(String val) { event.policyId = val; return this; }
        public Builder detectedAt(long val) { event.detectedAt = val; return this; }
        public Builder eventTime(long val) { event.eventTime = val; return this; }
        public Builder confidence(double val) { event.confidence = val; return this; }
        public Builder crashType(CrashType val) { event.crashType = val; return this; }
        public Builder severity(int val) { event.severity = val; return this; }
        public Builder maxGForce(double val) { event.maxGForce = val; return this; }
        public Builder maxRollRate(double val) { event.maxRollRate = val; return this; }
        public Builder speedAtImpact(double val) { event.speedAtImpact = val; return this; }
        public Builder deltaV(double val) { event.deltaV = val; return this; }
        public Builder latitude(double val) { event.latitude = val; return this; }
        public Builder longitude(double val) { event.longitude = val; return this; }
        public Builder address(String val) { event.address = val; return this; }
        public Builder windowStart(long val) { event.windowStart = val; return this; }
        public Builder windowEnd(long val) { event.windowEnd = val; return this; }
        public Builder eventCount(int val) { event.eventCount = val; return this; }
        public Builder signalScores(SignalScores val) { event.signalScores = val; return this; }
        public Builder isLateDetection(boolean val) { event.isLateDetection = val; return this; }
        public Builder latenessDurationMs(long val) { event.latenessDurationMs = val; return this; }
        public Builder modelVersion(String val) { event.modelVersion = val; return this; }
        public Builder detectionMethod(String val) { event.detectionMethod = val; return this; }

        public CrashEvent build() { return event; }
    }
}

/**
 * Types of crashes
 */
enum CrashType {
    FRONTAL,      // Head-on collision
    REAR,         // Rear-end collision
    SIDE_LEFT,    // Left side impact
    SIDE_RIGHT,   // Right side impact
    ROLLOVER,     // Vehicle rollover
    UNKNOWN       // Cannot determine type
}

/**
 * Signal scores from crash detection algorithm
 */
class SignalScores implements Serializable {
    private static final long serialVersionUID = 1L;

    private double gForceScore;
    private double gyroscopeScore;
    private double speedScore;
    private double gpsScore;

    public SignalScores() {}

    public SignalScores(double gForceScore, double gyroscopeScore,
                       double speedScore, double gpsScore) {
        this.gForceScore = gForceScore;
        this.gyroscopeScore = gyroscopeScore;
        this.speedScore = speedScore;
        this.gpsScore = gpsScore;
    }

    public double getGForceScore() { return gForceScore; }
    public double getGyroscopeScore() { return gyroscopeScore; }
    public double getSpeedScore() { return speedScore; }
    public double getGpsScore() { return gpsScore; }
}

/**
 * Vehicle baseline for anomaly detection
 */
class VehicleBaseline implements Serializable {
    private static final long serialVersionUID = 1L;

    private double avgGForce;
    private double avgSpeed;
    private double avgAcceleration;
    private long sampleCount;

    private static final double ALPHA = 0.1; // EMA smoothing factor

    public void updateWithNewData(Object analysis) {
        // Update exponential moving averages
        sampleCount++;
    }
}

