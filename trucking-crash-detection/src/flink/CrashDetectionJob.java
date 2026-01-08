package com.crashguard.flink;

import org.apache.flink.api.common.eventtime.WatermarkStrategy;
import org.apache.flink.api.common.functions.RichMapFunction;
import org.apache.flink.api.common.restartstrategy.RestartStrategies;
import org.apache.flink.api.common.state.ValueState;
import org.apache.flink.api.common.state.ValueStateDescriptor;
import org.apache.flink.api.common.time.Time;
import org.apache.flink.api.common.typeinfo.TypeInformation;
import org.apache.flink.configuration.Configuration;
import org.apache.flink.connector.kafka.sink.KafkaSink;
import org.apache.flink.connector.kafka.sink.KafkaRecordSerializationSchema;
import org.apache.flink.connector.kafka.source.KafkaSource;
import org.apache.flink.connector.kafka.source.enumerator.initializer.OffsetsInitializer;
import org.apache.flink.streaming.api.CheckpointingMode;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.datastream.SingleOutputStreamOperator;
import org.apache.flink.streaming.api.environment.CheckpointConfig;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.streaming.api.functions.KeyedProcessFunction;
import org.apache.flink.streaming.api.functions.windowing.ProcessWindowFunction;
import org.apache.flink.streaming.api.windowing.assigners.TumblingEventTimeWindows;
import org.apache.flink.streaming.api.windowing.windows.TimeWindow;
import org.apache.flink.util.Collector;
import org.apache.flink.util.OutputTag;

import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Properties;
import java.util.UUID;

/**
 * Apache Flink Job for Real-Time Crash Detection
 *
 * This job processes telemetry data from vehicles to detect crashes in real-time.
 * It handles:
 * - High-throughput streaming data (~10M events/sec)
 * - Out-of-order events due to network latency
 * - Late arriving data after network recovery
 * - Exactly-once processing semantics
 * - Fault tolerance with checkpointing
 *
 * @author CrashGuard Team
 */
public class CrashDetectionJob {

    // Side output for late events that arrive after the allowed lateness window
    private static final OutputTag<TelemetryEvent> LATE_EVENTS_TAG =
        new OutputTag<TelemetryEvent>("late-events") {};

    // Side output for events that need manual review
    private static final OutputTag<CrashEvent> REVIEW_REQUIRED_TAG =
        new OutputTag<CrashEvent>("review-required") {};

    public static void main(String[] args) throws Exception {
        // Create execution environment
        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();

        // Configure for production
        configureEnvironment(env);

        // Build the processing pipeline
        buildPipeline(env);

        // Execute
        env.execute("Crash Detection Pipeline v1.0");
    }

    /**
     * Configure Flink environment for production use
     */
    private static void configureEnvironment(StreamExecutionEnvironment env) {
        // ============================================
        // CHECKPOINTING - For fault tolerance
        // ============================================
        env.enableCheckpointing(1000); // Checkpoint every 1 second

        CheckpointConfig checkpointConfig = env.getCheckpointConfig();
        checkpointConfig.setCheckpointingMode(CheckpointingMode.EXACTLY_ONCE);
        checkpointConfig.setMinPauseBetweenCheckpoints(500); // Min 500ms between checkpoints
        checkpointConfig.setCheckpointTimeout(60000); // 60 second timeout
        checkpointConfig.setMaxConcurrentCheckpoints(1);
        checkpointConfig.setTolerableCheckpointFailureNumber(3);

        // Enable externalized checkpoints for recovery after job cancellation
        checkpointConfig.setExternalizedCheckpointCleanup(
            CheckpointConfig.ExternalizedCheckpointCleanup.RETAIN_ON_CANCELLATION);

        // ============================================
        // RESTART STRATEGY - Handle failures gracefully
        // ============================================
        env.setRestartStrategy(RestartStrategies.fixedDelayRestart(
            3,                          // Max 3 restart attempts
            Time.seconds(10)            // 10 second delay between restarts
        ));

        // ============================================
        // BUFFER TIMEOUT - For low latency
        // ============================================
        env.setBufferTimeout(10); // 10ms buffer timeout for low latency

        // ============================================
        // PARALLELISM - Scale based on cluster
        // ============================================
        env.setParallelism(64); // Adjust based on cluster size
    }

    /**
     * Build the main processing pipeline
     */
    private static void buildPipeline(StreamExecutionEnvironment env) {
        // ============================================
        // SOURCE: Kafka with Watermarks
        // ============================================
        KafkaSource<TelemetryEvent> kafkaSource = KafkaSource.<TelemetryEvent>builder()
            .setBootstrapServers(getKafkaBootstrapServers())
            .setTopics("normalized-telemetry")
            .setGroupId("crash-detection-v1")
            .setStartingOffsets(OffsetsInitializer.latest())
            .setValueOnlyDeserializer(new TelemetryEventDeserializer())
            // Handle consumer lag - important for recovery scenarios
            .setProperty("fetch.min.bytes", "1")
            .setProperty("fetch.max.wait.ms", "100")
            .setProperty("max.partition.fetch.bytes", "10485760") // 10MB
            .build();

        // ============================================
        // WATERMARK STRATEGY - Handle out-of-order and late data
        // ============================================
        WatermarkStrategy<TelemetryEvent> watermarkStrategy = WatermarkStrategy
            // Allow 5 seconds of out-of-orderness for network delays
            .<TelemetryEvent>forBoundedOutOfOrderness(Duration.ofSeconds(5))
            // Extract event time from the telemetry event
            .withTimestampAssigner((event, recordTimestamp) -> event.getEventTime())
            // Handle idle partitions (vehicles that stop sending data)
            .withIdleness(Duration.ofMinutes(1));

        DataStream<TelemetryEvent> telemetryStream = env.fromSource(
            kafkaSource,
            watermarkStrategy,
            "Kafka Telemetry Source"
        );

        // ============================================
        // CRASH DETECTION PIPELINE
        // ============================================
        SingleOutputStreamOperator<CrashEvent> crashEvents = telemetryStream
            // Key by vehicle for stateful processing
            .keyBy(TelemetryEvent::getVehicleId)
            // Use tumbling windows of 100ms for crash detection
            .window(TumblingEventTimeWindows.of(Duration.ofMillis(100)))
            // Allow late data up to 30 seconds (for network recovery scenarios)
            .allowedLateness(Duration.ofSeconds(30))
            // Send very late data to side output instead of dropping
            .sideOutputLateData(LATE_EVENTS_TAG)
            // Process the window
            .process(new CrashDetectionWindowFunction());

        // ============================================
        // HANDLE LATE ARRIVING DATA
        // ============================================
        DataStream<TelemetryEvent> lateEvents = crashEvents.getSideOutput(LATE_EVENTS_TAG);

        // Process late events separately - they may indicate crashes we missed
        SingleOutputStreamOperator<CrashEvent> lateCrashEvents = lateEvents
            .keyBy(TelemetryEvent::getVehicleId)
            .process(new LateEventProcessor());

        // ============================================
        // ENRICH WITH VEHICLE/POLICY DATA
        // ============================================
        DataStream<EnrichedCrashEvent> enrichedCrashEvents = crashEvents
            .map(new VehicleEnrichmentFunction())
            .name("Enrich with Vehicle Data");

        // ============================================
        // SEVERITY CLASSIFICATION (ML)
        // ============================================
        SingleOutputStreamOperator<EnrichedCrashEvent> classifiedEvents = enrichedCrashEvents
            .keyBy(EnrichedCrashEvent::getVehicleId)
            .process(new SeverityClassificationFunction())
            .name("ML Severity Classification");

        // ============================================
        // SINKS: Output to Kafka topics
        // ============================================

        // Main crash events sink
        KafkaSink<EnrichedCrashEvent> crashEventsSink = KafkaSink.<EnrichedCrashEvent>builder()
            .setBootstrapServers(getKafkaBootstrapServers())
            .setRecordSerializer(KafkaRecordSerializationSchema.builder()
                .setTopic("crash-events")
                .setValueSerializationSchema(new EnrichedCrashEventSerializer())
                .build())
            .setDeliveryGuarantee(org.apache.flink.connector.base.DeliveryGuarantee.EXACTLY_ONCE)
            .setTransactionalIdPrefix("crash-detection")
            .build();

        classifiedEvents
            .filter(event -> event.getConfidence() > 0.65)
            .sinkTo(crashEventsSink)
            .name("Crash Events Sink");

        // Late crash events sink (for monitoring)
        lateCrashEvents
            .map(event -> enrichEvent(event))
            .sinkTo(createLateCrashEventsSink())
            .name("Late Crash Events Sink");

        // Events requiring review
        DataStream<CrashEvent> reviewEvents = classifiedEvents.getSideOutput(REVIEW_REQUIRED_TAG);
        reviewEvents
            .sinkTo(createReviewQueueSink())
            .name("Review Queue Sink");
    }

    private static String getKafkaBootstrapServers() {
        return System.getenv().getOrDefault("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092");
    }

    // Helper methods for creating sinks (simplified)
    private static KafkaSink<EnrichedCrashEvent> createLateCrashEventsSink() {
        return KafkaSink.<EnrichedCrashEvent>builder()
            .setBootstrapServers(getKafkaBootstrapServers())
            .setRecordSerializer(KafkaRecordSerializationSchema.builder()
                .setTopic("late-crash-events")
                .setValueSerializationSchema(new EnrichedCrashEventSerializer())
                .build())
            .build();
    }

    private static KafkaSink<CrashEvent> createReviewQueueSink() {
        return KafkaSink.<CrashEvent>builder()
            .setBootstrapServers(getKafkaBootstrapServers())
            .setRecordSerializer(KafkaRecordSerializationSchema.builder()
                .setTopic("crash-review-queue")
                .setValueSerializationSchema(new CrashEventSerializer())
                .build())
            .build();
    }

    private static EnrichedCrashEvent enrichEvent(CrashEvent event) {
        // Simplified enrichment
        return new EnrichedCrashEvent(event);
    }
}

