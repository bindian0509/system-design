package com.urlshortener.config;

import lombok.Getter;

/**
 * Region configuration for global range allocation.
 *
 * Each region gets a dedicated range of IDs to ensure:
 * - Zero cross-region coordination for ID generation
 * - Guaranteed uniqueness across all regions
 * - Predictable capacity planning per region
 *
 * Total capacity: 62^7 = 3,521,614,606,208 unique codes
 * Split into 3 regions: ~1.17 trillion each
 */
@Getter
public enum RegionConfig {

    /**
     * US Region (Americas)
     * Range: 0 to 1,173,871,535,402
     * Codes start with: 0000000 to 0LY7VK2
     */
    US_EAST_1("us-east-1", "US", 0L, 1_173_871_535_402L),

    /**
     * EU Region (Europe)
     * Range: 1,173,871,535,403 to 2,347,743,070,805
     * Codes start with: 0LY7VK3 to 0zXdWV5
     */
    EU_WEST_1("eu-west-1", "EU", 1_173_871_535_403L, 2_347_743_070_805L),

    /**
     * India/Asia Region
     * Range: 2,347,743,070,806 to 3,521,614,606,207
     * Codes start with: 0zXdWV6 to ZZZZZZZ
     */
    AP_SOUTH_1("ap-south-1", "IN", 2_347_743_070_806L, 3_521_614_606_207L);

    private final String awsRegion;
    private final String shortCode;
    private final long rangeStart;
    private final long rangeEnd;

    RegionConfig(String awsRegion, String shortCode, long rangeStart, long rangeEnd) {
        this.awsRegion = awsRegion;
        this.shortCode = shortCode;
        this.rangeStart = rangeStart;
        this.rangeEnd = rangeEnd;
    }

    /**
     * Get the capacity of this region.
     */
    public long getCapacity() {
        return rangeEnd - rangeStart + 1;
    }

    /**
     * Get region config by AWS region name.
     */
    public static RegionConfig fromAwsRegion(String awsRegion) {
        for (RegionConfig config : values()) {
            if (config.awsRegion.equals(awsRegion)) {
                return config;
            }
        }
        // Default to US region if unknown
        return US_EAST_1;
    }

    /**
     * Determine which region a code belongs to based on its numeric value.
     */
    public static RegionConfig fromNumericValue(long value) {
        for (RegionConfig config : values()) {
            if (value >= config.rangeStart && value <= config.rangeEnd) {
                return config;
            }
        }
        throw new IllegalArgumentException("Value " + value + " is out of range");
    }
}
