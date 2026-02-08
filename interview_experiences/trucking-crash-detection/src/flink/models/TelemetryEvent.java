package com.crashguard.flink.models;

import java.io.Serializable;

/**
 * Telemetry event from vehicle sensors.
 * Represents normalized sensor data from telematics providers.
 */
public class TelemetryEvent implements Serializable {

    private static final long serialVersionUID = 1L;

    // Identifiers
    private String eventId;
    private String vehicleId;
    private String providerId;
    private String policyId;

    // Timestamps
    private long eventTime;        // When event occurred (event time)
    private long ingestionTime;    // When received by system (processing time)

    // GPS Data
    private double latitude;
    private double longitude;
    private double altitudeM;
    private double speedMps;       // meters per second
    private double headingDeg;
    private double gpsAccuracyM;

    // Accelerometer (G-force)
    private double accelX;         // Longitudinal (-/+ = brake/accel)
    private double accelY;         // Lateral (-/+ = left/right)
    private double accelZ;         // Vertical (1.0 = normal gravity)

    // Gyroscope (degrees per second)
    private double gyroRoll;       // Roll rate
    private double gyroPitch;      // Pitch rate
    private double gyroYaw;        // Yaw rate

    // Vehicle State
    private String ignitionState;  // on, off, accessory
    private double odometerKm;
    private double fuelLevelPct;
    private int engineRpm;

    // Quality
    private double qualityScore;

    // Constructors
    public TelemetryEvent() {}

    // Builder pattern
    public static Builder builder() {
        return new Builder();
    }

    // Getters
    public String getEventId() { return eventId; }
    public String getVehicleId() { return vehicleId; }
    public String getProviderId() { return providerId; }
    public String getPolicyId() { return policyId; }
    public long getEventTime() { return eventTime; }
    public long getIngestionTime() { return ingestionTime; }
    public double getLatitude() { return latitude; }
    public double getLongitude() { return longitude; }
    public double getAltitudeM() { return altitudeM; }
    public double getSpeedMps() { return speedMps; }
    public double getHeadingDeg() { return headingDeg; }
    public double getGpsAccuracyM() { return gpsAccuracyM; }
    public double getAccelX() { return accelX; }
    public double getAccelY() { return accelY; }
    public double getAccelZ() { return accelZ; }
    public double getGyroRoll() { return gyroRoll; }
    public double getGyroPitch() { return gyroPitch; }
    public double getGyroYaw() { return gyroYaw; }
    public String getIgnitionState() { return ignitionState; }
    public double getOdometerKm() { return odometerKm; }
    public double getFuelLevelPct() { return fuelLevelPct; }
    public int getEngineRpm() { return engineRpm; }
    public double getQualityScore() { return qualityScore; }

    // Setters
    public void setEventId(String eventId) { this.eventId = eventId; }
    public void setVehicleId(String vehicleId) { this.vehicleId = vehicleId; }
    public void setProviderId(String providerId) { this.providerId = providerId; }
    public void setPolicyId(String policyId) { this.policyId = policyId; }
    public void setEventTime(long eventTime) { this.eventTime = eventTime; }
    public void setIngestionTime(long ingestionTime) { this.ingestionTime = ingestionTime; }
    public void setLatitude(double latitude) { this.latitude = latitude; }
    public void setLongitude(double longitude) { this.longitude = longitude; }
    public void setAltitudeM(double altitudeM) { this.altitudeM = altitudeM; }
    public void setSpeedMps(double speedMps) { this.speedMps = speedMps; }
    public void setHeadingDeg(double headingDeg) { this.headingDeg = headingDeg; }
    public void setGpsAccuracyM(double gpsAccuracyM) { this.gpsAccuracyM = gpsAccuracyM; }
    public void setAccelX(double accelX) { this.accelX = accelX; }
    public void setAccelY(double accelY) { this.accelY = accelY; }
    public void setAccelZ(double accelZ) { this.accelZ = accelZ; }
    public void setGyroRoll(double gyroRoll) { this.gyroRoll = gyroRoll; }
    public void setGyroPitch(double gyroPitch) { this.gyroPitch = gyroPitch; }
    public void setGyroYaw(double gyroYaw) { this.gyroYaw = gyroYaw; }
    public void setIgnitionState(String ignitionState) { this.ignitionState = ignitionState; }
    public void setOdometerKm(double odometerKm) { this.odometerKm = odometerKm; }
    public void setFuelLevelPct(double fuelLevelPct) { this.fuelLevelPct = fuelLevelPct; }
    public void setEngineRpm(int engineRpm) { this.engineRpm = engineRpm; }
    public void setQualityScore(double qualityScore) { this.qualityScore = qualityScore; }

    public static class Builder {
        private final TelemetryEvent event = new TelemetryEvent();

        public Builder eventId(String val) { event.eventId = val; return this; }
        public Builder vehicleId(String val) { event.vehicleId = val; return this; }
        public Builder providerId(String val) { event.providerId = val; return this; }
        public Builder policyId(String val) { event.policyId = val; return this; }
        public Builder eventTime(long val) { event.eventTime = val; return this; }
        public Builder ingestionTime(long val) { event.ingestionTime = val; return this; }
        public Builder latitude(double val) { event.latitude = val; return this; }
        public Builder longitude(double val) { event.longitude = val; return this; }
        public Builder speedMps(double val) { event.speedMps = val; return this; }
        public Builder accelX(double val) { event.accelX = val; return this; }
        public Builder accelY(double val) { event.accelY = val; return this; }
        public Builder accelZ(double val) { event.accelZ = val; return this; }
        public Builder gyroRoll(double val) { event.gyroRoll = val; return this; }
        public Builder gyroPitch(double val) { event.gyroPitch = val; return this; }
        public Builder gyroYaw(double val) { event.gyroYaw = val; return this; }

        public TelemetryEvent build() { return event; }
    }
}


