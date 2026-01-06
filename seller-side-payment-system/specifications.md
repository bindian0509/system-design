# Seller Payment System - Java Spring Boot Implementation Specification

This document provides complete specifications for an AI agent to generate the full Java Spring Boot implementation of the Seller-Side Payment System.

## Project Overview

Build a production-ready seller payment system that:
- Processes order completion events and updates seller balances
- Schedules and executes payouts based on seller preferences
- Integrates with a third-party payment gateway
- Provides REST APIs for sellers, admins, and internal services
- Maintains comprehensive audit logs

## Technology Stack

| Component | Technology | Version |
|-----------|------------|---------|
| Language | Java | 17+ |
| Framework | Spring Boot | 3.2.x |
| Build Tool | Maven | 3.9.x |
| Database | PostgreSQL | 15+ |
| ORM | Spring Data JPA / Hibernate | - |
| Cache | Redis | 7.x |
| Message Queue | Apache Kafka | 3.x |
| API Documentation | SpringDoc OpenAPI | 2.x |
| Testing | JUnit 5, Mockito, Testcontainers | - |

---

## Project Structure

```
seller-payment-system/
├── pom.xml
├── src/
│   ├── main/
│   │   ├── java/com/ecommerce/sellerpayment/
│   │   │   ├── SellerPaymentApplication.java
│   │   │   ├── config/
│   │   │   │   ├── KafkaConfig.java
│   │   │   │   ├── RedisConfig.java
│   │   │   │   ├── SchedulerConfig.java
│   │   │   │   ├── SecurityConfig.java
│   │   │   │   └── OpenApiConfig.java
│   │   │   ├── entity/
│   │   │   │   ├── SellerPayoutPreference.java
│   │   │   │   ├── SellerBalance.java
│   │   │   │   ├── PayoutRecord.java
│   │   │   │   ├── OrderPayoutMapping.java
│   │   │   │   ├── AuditLog.java
│   │   │   │   └── enums/
│   │   │   │       ├── PayoutSchedule.java
│   │   │   │       ├── PaymentMethod.java
│   │   │   │       ├── PayoutStatus.java
│   │   │   │       ├── MappingStatus.java
│   │   │   │       └── AuditEventType.java
│   │   │   ├── repository/
│   │   │   │   ├── SellerPayoutPreferenceRepository.java
│   │   │   │   ├── SellerBalanceRepository.java
│   │   │   │   ├── PayoutRecordRepository.java
│   │   │   │   ├── OrderPayoutMappingRepository.java
│   │   │   │   └── AuditLogRepository.java
│   │   │   ├── dto/
│   │   │   │   ├── request/
│   │   │   │   │   ├── OnDemandPayoutRequest.java
│   │   │   │   │   ├── UpdatePreferencesRequest.java
│   │   │   │   │   ├── OrderEventRequest.java
│   │   │   │   │   ├── RetryPayoutRequest.java
│   │   │   │   │   ├── CancelPayoutRequest.java
│   │   │   │   │   ├── ManualPayoutRequest.java
│   │   │   │   │   └── BalanceAdjustmentRequest.java
│   │   │   │   ├── response/
│   │   │   │   │   ├── PaymentStatusResponse.java
│   │   │   │   │   ├── PayoutDetailsResponse.java
│   │   │   │   │   ├── PayoutHistoryResponse.java
│   │   │   │   │   ├── EarningsResponse.java
│   │   │   │   │   ├── PreferencesResponse.java
│   │   │   │   │   └── ApiErrorResponse.java
│   │   │   │   └── event/
│   │   │   │       ├── OrderCompletedEvent.java
│   │   │   │       ├── OrderCancelledEvent.java
│   │   │   │       └── ProductInfo.java
│   │   │   ├── service/
│   │   │   │   ├── BalanceService.java
│   │   │   │   ├── PayoutSchedulerService.java
│   │   │   │   ├── PaymentProcessorService.java
│   │   │   │   ├── AuditService.java
│   │   │   │   ├── ReconciliationService.java
│   │   │   │   ├── SellerPaymentDetailsService.java
│   │   │   │   └── impl/
│   │   │   │       ├── BalanceServiceImpl.java
│   │   │   │       ├── PayoutSchedulerServiceImpl.java
│   │   │   │       ├── PaymentProcessorServiceImpl.java
│   │   │   │       ├── AuditServiceImpl.java
│   │   │   │       ├── ReconciliationServiceImpl.java
│   │   │   │       └── SellerPaymentDetailsServiceImpl.java
│   │   │   ├── gateway/
│   │   │   │   ├── PaymentGateway.java
│   │   │   │   ├── PaymentGatewayResponse.java
│   │   │   │   ├── WireDetails.java
│   │   │   │   ├── CheckDetails.java
│   │   │   │   └── impl/
│   │   │   │       └── ThirdPartyPaymentGateway.java
│   │   │   ├── consumer/
│   │   │   │   └── OrderEventConsumer.java
│   │   │   ├── scheduler/
│   │   │   │   ├── PayoutSchedulerJob.java
│   │   │   │   ├── SettlementProcessorJob.java
│   │   │   │   └── ReconciliationJob.java
│   │   │   ├── controller/
│   │   │   │   ├── SellerPaymentController.java
│   │   │   │   ├── InternalController.java
│   │   │   │   └── AdminController.java
│   │   │   ├── exception/
│   │   │   │   ├── GlobalExceptionHandler.java
│   │   │   │   ├── InsufficientBalanceException.java
│   │   │   │   ├── PayoutInProgressException.java
│   │   │   │   ├── PayoutNotFoundException.java
│   │   │   │   ├── SellerNotFoundException.java
│   │   │   │   ├── InvalidStatusTransitionException.java
│   │   │   │   └── GatewayException.java
│   │   │   └── util/
│   │   │       ├── IdGenerator.java
│   │   │       └── CircuitBreaker.java
│   │   └── resources/
│   │       ├── application.yml
│   │       ├── application-dev.yml
│   │       ├── application-prod.yml
│   │       └── db/migration/
│   │           ├── V1__create_seller_payout_preference.sql
│   │           ├── V2__create_seller_balance.sql
│   │           ├── V3__create_payout_record.sql
│   │           ├── V4__create_order_payout_mapping.sql
│   │           └── V5__create_audit_log.sql
│   └── test/
│       └── java/com/ecommerce/sellerpayment/
│           ├── service/
│           │   ├── BalanceServiceTest.java
│           │   ├── PaymentProcessorServiceTest.java
│           │   └── PayoutSchedulerServiceTest.java
│           ├── controller/
│           │   ├── SellerPaymentControllerTest.java
│           │   └── AdminControllerTest.java
│           └── integration/
│               └── PaymentFlowIntegrationTest.java
└── docker-compose.yml
```

---

## Maven Dependencies (pom.xml)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>3.2.0</version>
    </parent>

    <groupId>com.ecommerce</groupId>
    <artifactId>seller-payment-system</artifactId>
    <version>1.0.0</version>
    <name>Seller Payment System</name>

    <properties>
        <java.version>17</java.version>
    </properties>

    <dependencies>
        <!-- Spring Boot Starters -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-data-jpa</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-data-redis</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-validation</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-actuator</artifactId>
        </dependency>

        <!-- Kafka -->
        <dependency>
            <groupId>org.springframework.kafka</groupId>
            <artifactId>spring-kafka</artifactId>
        </dependency>

        <!-- Database -->
        <dependency>
            <groupId>org.postgresql</groupId>
            <artifactId>postgresql</artifactId>
            <scope>runtime</scope>
        </dependency>
        <dependency>
            <groupId>org.flywaydb</groupId>
            <artifactId>flyway-core</artifactId>
        </dependency>

        <!-- Redis -->
        <dependency>
            <groupId>org.redisson</groupId>
            <artifactId>redisson-spring-boot-starter</artifactId>
            <version>3.24.0</version>
        </dependency>

        <!-- OpenAPI Documentation -->
        <dependency>
            <groupId>org.springdoc</groupId>
            <artifactId>springdoc-openapi-starter-webmvc-ui</artifactId>
            <version>2.2.0</version>
        </dependency>

        <!-- Utilities -->
        <dependency>
            <groupId>org.projectlombok</groupId>
            <artifactId>lombok</artifactId>
            <optional>true</optional>
        </dependency>
        <dependency>
            <groupId>org.mapstruct</groupId>
            <artifactId>mapstruct</artifactId>
            <version>1.5.5.Final</version>
        </dependency>

        <!-- Testing -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>org.springframework.kafka</groupId>
            <artifactId>spring-kafka-test</artifactId>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>org.testcontainers</groupId>
            <artifactId>postgresql</artifactId>
            <version>1.19.0</version>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>org.testcontainers</groupId>
            <artifactId>kafka</artifactId>
            <version>1.19.0</version>
            <scope>test</scope>
        </dependency>
    </dependencies>
</project>
```

---

## Entity Specifications

### 1. Enums

```java
// PayoutSchedule.java
public enum PayoutSchedule {
    DAILY,
    WEEKLY,
    THRESHOLD,
    ON_DEMAND
}

// PaymentMethod.java
public enum PaymentMethod {
    CHECK,
    WIRE
}

// PayoutStatus.java
public enum PayoutStatus {
    PENDING,
    PROCESSING,
    COMPLETED,
    FAILED,
    CANCELLED
}

// MappingStatus.java
public enum MappingStatus {
    PENDING,
    SETTLED,
    CANCELLED,
    PAID
}

// AuditEventType.java
public enum AuditEventType {
    PAYOUT_CREATED,
    PAYOUT_SUBMITTED,
    PAYOUT_COMPLETED,
    PAYOUT_FAILED,
    PAYOUT_RETRY,
    PAYOUT_CANCELLED,
    BALANCE_CREDITED,
    BALANCE_DEBITED,
    BALANCE_HELD,
    BALANCE_RELEASED,
    PREFERENCE_UPDATED,
    MANUAL_ADJUSTMENT
}
```

### 2. SellerPayoutPreference Entity

```java
@Entity
@Table(name = "seller_payout_preference")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class SellerPayoutPreference {

    @Id
    @Column(name = "seller_id", length = 50)
    private String sellerId;

    @Enumerated(EnumType.STRING)
    @Column(name = "payout_schedule", nullable = false, length = 20)
    private PayoutSchedule payoutSchedule = PayoutSchedule.WEEKLY;

    @Column(name = "threshold_amount", precision = 15, scale = 2)
    private BigDecimal thresholdAmount = BigDecimal.valueOf(100.00);

    @Column(name = "preferred_day")
    private Integer preferredDay = 5; // Friday

    @Enumerated(EnumType.STRING)
    @Column(name = "payment_method", nullable = false, length = 10)
    private PaymentMethod paymentMethod = PaymentMethod.WIRE;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    @PrePersist
    protected void onCreate() {
        createdAt = Instant.now();
        updatedAt = Instant.now();
    }

    @PreUpdate
    protected void onUpdate() {
        updatedAt = Instant.now();
    }
}
```

### 3. SellerBalance Entity

```java
@Entity
@Table(name = "seller_balance")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class SellerBalance {

    @Id
    @Column(name = "seller_id", length = 50)
    private String sellerId;

    @Column(name = "available_balance", nullable = false, precision = 15, scale = 2)
    private BigDecimal availableBalance = BigDecimal.ZERO;

    @Column(name = "pending_balance", nullable = false, precision = 15, scale = 2)
    private BigDecimal pendingBalance = BigDecimal.ZERO;

    @Column(name = "held_balance", nullable = false, precision = 15, scale = 2)
    private BigDecimal heldBalance = BigDecimal.ZERO;

    @Version
    @Column(name = "version", nullable = false)
    private Long version = 0L;

    @Column(name = "last_updated", nullable = false)
    private Instant lastUpdated;

    @PrePersist
    @PreUpdate
    protected void onUpdate() {
        lastUpdated = Instant.now();
    }

    public BigDecimal getTotalBalance() {
        return availableBalance.add(pendingBalance).add(heldBalance);
    }
}
```

### 4. PayoutRecord Entity

```java
@Entity
@Table(name = "payout_record")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class PayoutRecord {

    @Id
    @Column(name = "payout_id", length = 100)
    private String payoutId;

    @Column(name = "seller_id", nullable = false, length = 50)
    private String sellerId;

    @Column(name = "amount", nullable = false, precision = 15, scale = 2)
    private BigDecimal amount;

    @Enumerated(EnumType.STRING)
    @Column(name = "payment_method", nullable = false, length = 10)
    private PaymentMethod paymentMethod;

    @Enumerated(EnumType.STRING)
    @Column(name = "status", nullable = false, length = 20)
    private PayoutStatus status = PayoutStatus.PENDING;

    @Column(name = "gateway_txn_id", length = 100)
    private String gatewayTxnId;

    @Column(name = "error_code", length = 50)
    private String errorCode;

    @Column(name = "error_message", length = 500)
    private String errorMessage;

    @Column(name = "retry_count", nullable = false)
    private Integer retryCount = 0;

    @Column(name = "period_start", nullable = false)
    private Instant periodStart;

    @Column(name = "period_end", nullable = false)
    private Instant periodEnd;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    @Column(name = "processed_at")
    private Instant processedAt;

    @Column(name = "completed_at")
    private Instant completedAt;

    @PrePersist
    protected void onCreate() {
        createdAt = Instant.now();
    }
}
```

### 5. OrderPayoutMapping Entity

```java
@Entity
@Table(name = "order_payout_mapping")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class OrderPayoutMapping {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "order_id", nullable = false, length = 50)
    private String orderId;

    @Column(name = "payout_id", length = 100)
    private String payoutId;

    @Column(name = "seller_id", nullable = false, length = 50)
    private String sellerId;

    @Column(name = "seller_amount", nullable = false, precision = 15, scale = 2)
    private BigDecimal sellerAmount;

    @Enumerated(EnumType.STRING)
    @Column(name = "status", nullable = false, length = 20)
    private MappingStatus status = MappingStatus.PENDING;

    @Column(name = "order_timestamp", nullable = false)
    private Instant orderTimestamp;

    @Column(name = "settlement_date")
    private Instant settlementDate;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    @PrePersist
    protected void onCreate() {
        createdAt = Instant.now();
    }
}
```

### 6. AuditLog Entity

```java
@Entity
@Table(name = "audit_log")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class AuditLog {

    @Id
    @Column(name = "audit_id", length = 100)
    private String auditId;

    @Column(name = "payout_id", length = 100)
    private String payoutId;

    @Column(name = "seller_id", nullable = false, length = 50)
    private String sellerId;

    @Enumerated(EnumType.STRING)
    @Column(name = "event_type", nullable = false, length = 30)
    private AuditEventType eventType;

    @Column(name = "previous_state", columnDefinition = "jsonb")
    @Convert(converter = JsonConverter.class)
    private Map<String, Object> previousState;

    @Column(name = "new_state", columnDefinition = "jsonb")
    @Convert(converter = JsonConverter.class)
    private Map<String, Object> newState;

    @Column(name = "actor", nullable = false, length = 100)
    private String actor;

    @Column(name = "timestamp", nullable = false)
    private Instant timestamp;

    @Column(name = "metadata", columnDefinition = "jsonb")
    @Convert(converter = JsonConverter.class)
    private Map<String, Object> metadata;

    @PrePersist
    protected void onCreate() {
        if (timestamp == null) {
            timestamp = Instant.now();
        }
    }
}
```

---

## Repository Specifications

### 1. SellerBalanceRepository

```java
public interface SellerBalanceRepository extends JpaRepository<SellerBalance, String> {

    @Lock(LockModeType.OPTIMISTIC)
    Optional<SellerBalance> findBySellerId(String sellerId);

    @Query("SELECT sb FROM SellerBalance sb WHERE sb.availableBalance > 0")
    List<SellerBalance> findAllWithAvailableBalance();

    @Query("""
        SELECT sb FROM SellerBalance sb
        JOIN SellerPayoutPreference spp ON sb.sellerId = spp.sellerId
        WHERE spp.payoutSchedule = :schedule
        AND sb.availableBalance > 0
        """)
    List<SellerBalance> findEligibleForSchedule(@Param("schedule") PayoutSchedule schedule);

    @Query("""
        SELECT sb FROM SellerBalance sb
        JOIN SellerPayoutPreference spp ON sb.sellerId = spp.sellerId
        WHERE spp.payoutSchedule = 'THRESHOLD'
        AND sb.availableBalance >= spp.thresholdAmount
        """)
    List<SellerBalance> findEligibleForThreshold();

    @Modifying
    @Query("""
        UPDATE SellerBalance sb
        SET sb.availableBalance = sb.availableBalance - :amount,
            sb.version = sb.version + 1,
            sb.lastUpdated = CURRENT_TIMESTAMP
        WHERE sb.sellerId = :sellerId
        AND sb.version = :version
        AND sb.availableBalance >= :amount
        """)
    int deductAvailableBalance(
        @Param("sellerId") String sellerId,
        @Param("amount") BigDecimal amount,
        @Param("version") Long version
    );

    @Modifying
    @Query("""
        UPDATE SellerBalance sb
        SET sb.pendingBalance = sb.pendingBalance + :amount,
            sb.version = sb.version + 1,
            sb.lastUpdated = CURRENT_TIMESTAMP
        WHERE sb.sellerId = :sellerId
        """)
    int creditPendingBalance(
        @Param("sellerId") String sellerId,
        @Param("amount") BigDecimal amount
    );
}
```

### 2. PayoutRecordRepository

```java
public interface PayoutRecordRepository extends JpaRepository<PayoutRecord, String> {

    List<PayoutRecord> findBySellerIdOrderByCreatedAtDesc(String sellerId);

    Page<PayoutRecord> findBySellerIdOrderByCreatedAtDesc(String sellerId, Pageable pageable);

    @Query("SELECT pr FROM PayoutRecord pr WHERE pr.sellerId = :sellerId AND pr.status IN :statuses")
    List<PayoutRecord> findBySellerIdAndStatusIn(
        @Param("sellerId") String sellerId,
        @Param("statuses") List<PayoutStatus> statuses
    );

    boolean existsBySellerIdAndStatusIn(String sellerId, List<PayoutStatus> statuses);

    @Query("""
        SELECT pr FROM PayoutRecord pr
        WHERE pr.status = 'PROCESSING'
        AND pr.processedAt < :cutoffTime
        """)
    List<PayoutRecord> findStuckProcessingPayouts(@Param("cutoffTime") Instant cutoffTime);

    @Query("SELECT pr FROM PayoutRecord pr WHERE pr.status = 'PENDING' ORDER BY pr.createdAt")
    List<PayoutRecord> findAllPendingPayouts();

    Optional<PayoutRecord> findByGatewayTxnId(String gatewayTxnId);

    @Query("""
        SELECT pr FROM PayoutRecord pr
        WHERE pr.sellerId = :sellerId
        AND pr.periodStart = :periodStart
        AND pr.periodEnd = :periodEnd
        AND pr.status NOT IN ('CANCELLED', 'FAILED')
        """)
    Optional<PayoutRecord> findExistingPayout(
        @Param("sellerId") String sellerId,
        @Param("periodStart") Instant periodStart,
        @Param("periodEnd") Instant periodEnd
    );
}
```

### 3. OrderPayoutMappingRepository

```java
public interface OrderPayoutMappingRepository extends JpaRepository<OrderPayoutMapping, Long> {

    Optional<OrderPayoutMapping> findByOrderIdAndSellerId(String orderId, String sellerId);

    boolean existsByOrderIdAndSellerId(String orderId, String sellerId);

    List<OrderPayoutMapping> findBySellerIdAndStatus(String sellerId, MappingStatus status);

    @Query("""
        SELECT opm FROM OrderPayoutMapping opm
        WHERE opm.status = 'PENDING'
        AND opm.orderTimestamp < :settlementCutoff
        """)
    List<OrderPayoutMapping> findReadyForSettlement(@Param("settlementCutoff") Instant settlementCutoff);

    @Query("""
        SELECT opm FROM OrderPayoutMapping opm
        WHERE opm.sellerId = :sellerId
        AND opm.status = 'SETTLED'
        AND opm.payoutId IS NULL
        """)
    List<OrderPayoutMapping> findSettledUnpaidBySeller(@Param("sellerId") String sellerId);

    @Modifying
    @Query("""
        UPDATE OrderPayoutMapping opm
        SET opm.status = 'PAID', opm.payoutId = :payoutId
        WHERE opm.sellerId = :sellerId
        AND opm.status = 'SETTLED'
        AND opm.payoutId IS NULL
        """)
    int markAsPaid(@Param("sellerId") String sellerId, @Param("payoutId") String payoutId);

    Page<OrderPayoutMapping> findBySellerIdOrderByCreatedAtDesc(String sellerId, Pageable pageable);
}
```

---

## Service Interface Specifications

### 1. BalanceService

```java
public interface BalanceService {

    SellerBalance getBalance(String sellerId);

    void creditPendingBalance(String sellerId, BigDecimal amount, String orderId);

    void moveToAvailable(String sellerId, BigDecimal amount);

    void deductForPayout(String sellerId, BigDecimal amount);

    void holdBalance(String sellerId, BigDecimal amount, String reason);

    void releaseHold(String sellerId, BigDecimal amount, String reason);

    void processOrderCancellation(String orderId, String sellerId);
}
```

### 2. PayoutSchedulerService

```java
public interface PayoutSchedulerService {

    void scheduleDailyPayouts();

    void scheduleWeeklyPayouts(DayOfWeek dayOfWeek);

    void scheduleThresholdPayouts();

    void processOnDemandPayout(String sellerId, BigDecimal amount);

    List<String> getEligibleSellers(PayoutSchedule schedule);

    PayoutRecord createPayoutRecord(String sellerId, BigDecimal amount, PaymentMethod method);
}
```

### 3. PaymentProcessorService

```java
public interface PaymentProcessorService {

    void processPayouts();

    void processPayout(PayoutRecord payout);

    void retryFailedPayout(String payoutId);

    void cancelPayout(String payoutId, String reason, boolean returnToBalance);

    PayoutRecord createManualPayout(String sellerId, BigDecimal amount, String reason);
}
```

### 4. AuditService

```java
public interface AuditService {

    void logPayoutCreated(PayoutRecord payout);

    void logPayoutSubmitted(PayoutRecord payout);

    void logPayoutCompleted(PayoutRecord payout, String gatewayTxnId);

    void logPayoutFailed(PayoutRecord payout, String errorCode, String errorMessage);

    void logBalanceCredited(String sellerId, BigDecimal amount, String orderId);

    void logBalanceDebited(String sellerId, BigDecimal amount, String payoutId);

    void logEvent(String sellerId, String payoutId, AuditEventType eventType,
                  Map<String, Object> previousState, Map<String, Object> newState,
                  String actor, Map<String, Object> metadata);

    Page<AuditLog> getAuditTrail(String sellerId, String payoutId, Pageable pageable);
}
```

---

## Payment Gateway Interface

```java
public interface PaymentGateway {

    PaymentGatewayResponse sendWire(WireDetails wireDetails, BigDecimal amount, String referenceId);

    PaymentGatewayResponse sendCheck(CheckDetails checkDetails, BigDecimal amount, String referenceId);

    PaymentGatewayResponse getTransactionStatus(String transactionId);
}

@Data
@Builder
public class PaymentGatewayResponse {
    private boolean success;
    private String transactionId;
    private String errorCode;
    private String errorMessage;
    private Instant processedAt;
}

@Data
@Builder
public class WireDetails {
    private String bankName;
    private String accountNumber;
    private String routingNumber;
    private String accountHolderName;
    private String swiftCode;
}

@Data
@Builder
public class CheckDetails {
    private String payeeName;
    private String addressLine1;
    private String addressLine2;
    private String city;
    private String state;
    private String zipCode;
    private String memo;
}
```

---

## Controller Specifications

### 1. SellerPaymentController

```java
@RestController
@RequestMapping("/api/v1/sellers/{sellerId}/payments")
@Tag(name = "Seller Payments", description = "Seller-facing payment APIs")
public class SellerPaymentController {

    @GetMapping("/status")
    @Operation(summary = "Get payment status and balance")
    public ResponseEntity<PaymentStatusResponse> getPaymentStatus(
        @PathVariable String sellerId
    );

    @GetMapping("/{payoutId}")
    @Operation(summary = "Get payout details")
    public ResponseEntity<PayoutDetailsResponse> getPayoutDetails(
        @PathVariable String sellerId,
        @PathVariable String payoutId
    );

    @GetMapping("/history")
    @Operation(summary = "Get payout history")
    public ResponseEntity<PayoutHistoryResponse> getPayoutHistory(
        @PathVariable String sellerId,
        @RequestParam(defaultValue = "0") int page,
        @RequestParam(defaultValue = "20") int size,
        @RequestParam(required = false) PayoutStatus status,
        @RequestParam(required = false) @DateTimeFormat(iso = ISO.DATE_TIME) Instant from,
        @RequestParam(required = false) @DateTimeFormat(iso = ISO.DATE_TIME) Instant to
    );

    @PostMapping("/request")
    @Operation(summary = "Request on-demand payout")
    public ResponseEntity<PayoutDetailsResponse> requestPayout(
        @PathVariable String sellerId,
        @Valid @RequestBody OnDemandPayoutRequest request
    );

    @GetMapping("/preferences")
    @Operation(summary = "Get payout preferences")
    public ResponseEntity<PreferencesResponse> getPreferences(
        @PathVariable String sellerId
    );

    @PutMapping("/preferences")
    @Operation(summary = "Update payout preferences")
    public ResponseEntity<PreferencesResponse> updatePreferences(
        @PathVariable String sellerId,
        @Valid @RequestBody UpdatePreferencesRequest request
    );

    @GetMapping("/earnings")
    @Operation(summary = "Get earnings breakdown by order")
    public ResponseEntity<EarningsResponse> getEarnings(
        @PathVariable String sellerId,
        @RequestParam(defaultValue = "0") int page,
        @RequestParam(defaultValue = "20") int size,
        @RequestParam(required = false) MappingStatus status
    );
}
```

### 2. AdminController

```java
@RestController
@RequestMapping("/admin/v1")
@Tag(name = "Admin Operations", description = "Administrative APIs")
public class AdminController {

    @GetMapping("/payouts")
    @Operation(summary = "Search payouts")
    public ResponseEntity<Page<PayoutRecord>> searchPayouts(
        @RequestParam(required = false) String sellerId,
        @RequestParam(required = false) PayoutStatus status,
        @RequestParam(required = false) PaymentMethod paymentMethod,
        @RequestParam(required = false) BigDecimal minAmount,
        @RequestParam(required = false) BigDecimal maxAmount,
        @RequestParam(defaultValue = "0") int page,
        @RequestParam(defaultValue = "20") int size
    );

    @PostMapping("/payouts/{payoutId}/retry")
    @Operation(summary = "Retry failed payout")
    public ResponseEntity<PayoutRecord> retryPayout(
        @PathVariable String payoutId,
        @Valid @RequestBody RetryPayoutRequest request
    );

    @PostMapping("/payouts/{payoutId}/cancel")
    @Operation(summary = "Cancel payout")
    public ResponseEntity<PayoutRecord> cancelPayout(
        @PathVariable String payoutId,
        @Valid @RequestBody CancelPayoutRequest request
    );

    @PostMapping("/payouts/manual")
    @Operation(summary = "Create manual payout")
    public ResponseEntity<PayoutRecord> createManualPayout(
        @Valid @RequestBody ManualPayoutRequest request
    );

    @PostMapping("/sellers/{sellerId}/balance/adjust")
    @Operation(summary = "Adjust seller balance")
    public ResponseEntity<SellerBalance> adjustBalance(
        @PathVariable String sellerId,
        @Valid @RequestBody BalanceAdjustmentRequest request
    );

    @GetMapping("/audit")
    @Operation(summary = "Get audit trail")
    public ResponseEntity<Page<AuditLog>> getAuditTrail(
        @RequestParam(required = false) String sellerId,
        @RequestParam(required = false) String payoutId,
        @RequestParam(required = false) AuditEventType eventType,
        @RequestParam(defaultValue = "0") int page,
        @RequestParam(defaultValue = "50") int size
    );
}
```

### 3. InternalController

```java
@RestController
@RequestMapping("/internal/v1")
@Tag(name = "Internal APIs", description = "Service-to-service communication")
public class InternalController {

    @PostMapping("/orders/events")
    @Operation(summary = "Process order event")
    public ResponseEntity<Void> processOrderEvent(
        @Valid @RequestBody OrderEventRequest request
    );

    @GetMapping("/sellers/{sellerId}/payment-details")
    @Operation(summary = "Get seller payment details")
    public ResponseEntity<SellerPaymentDetailsResponse> getPaymentDetails(
        @PathVariable String sellerId
    );

    @PostMapping("/webhooks/payment-gateway")
    @Operation(summary = "Handle payment gateway webhook")
    public ResponseEntity<Void> handleGatewayWebhook(
        @RequestBody Map<String, Object> webhookPayload
    );
}
```

---

## Scheduled Jobs

### 1. PayoutSchedulerJob

```java
@Component
@Slf4j
public class PayoutSchedulerJob {

    private final PayoutSchedulerService schedulerService;
    private final RedissonClient redisson;

    private static final String SCHEDULER_LOCK = "payout_scheduler_leader";

    @Scheduled(cron = "0 0 22 * * *") // 10 PM daily
    public void runDailyPayouts() {
        RLock lock = redisson.getLock(SCHEDULER_LOCK);
        try {
            if (lock.tryLock(0, 30, TimeUnit.MINUTES)) {
                log.info("Acquired leader lock, running daily payouts");
                schedulerService.scheduleDailyPayouts();

                DayOfWeek today = LocalDate.now().getDayOfWeek();
                schedulerService.scheduleWeeklyPayouts(today);
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        } finally {
            if (lock.isHeldByCurrentThread()) {
                lock.unlock();
            }
        }
    }

    @Scheduled(fixedRate = 900000) // Every 15 minutes
    public void runThresholdPayouts() {
        RLock lock = redisson.getLock(SCHEDULER_LOCK + "_threshold");
        try {
            if (lock.tryLock(0, 10, TimeUnit.MINUTES)) {
                log.info("Running threshold-based payouts");
                schedulerService.scheduleThresholdPayouts();
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        } finally {
            if (lock.isHeldByCurrentThread()) {
                lock.unlock();
            }
        }
    }
}
```

### 2. SettlementProcessorJob

```java
@Component
@Slf4j
public class SettlementProcessorJob {

    private final BalanceService balanceService;
    private final OrderPayoutMappingRepository mappingRepository;

    @Scheduled(cron = "0 0 * * * *") // Every hour
    @Transactional
    public void processSettlements() {
        log.info("Processing settlements for orders past 7-day window");

        Instant cutoff = Instant.now().minus(7, ChronoUnit.DAYS);
        List<OrderPayoutMapping> readyMappings = mappingRepository.findReadyForSettlement(cutoff);

        for (OrderPayoutMapping mapping : readyMappings) {
            try {
                balanceService.moveToAvailable(mapping.getSellerId(), mapping.getSellerAmount());
                mapping.setStatus(MappingStatus.SETTLED);
                mapping.setSettlementDate(Instant.now());
                mappingRepository.save(mapping);

                log.info("Settled order {} for seller {}", mapping.getOrderId(), mapping.getSellerId());
            } catch (Exception e) {
                log.error("Failed to settle order {}: {}", mapping.getOrderId(), e.getMessage());
            }
        }
    }
}
```

### 3. ReconciliationJob

```java
@Component
@Slf4j
public class ReconciliationJob {

    private final PayoutRecordRepository payoutRepository;
    private final PaymentGateway paymentGateway;
    private final PaymentProcessorService processorService;

    @Scheduled(fixedRate = 900000) // Every 15 minutes
    public void reconcileStuckPayouts() {
        log.info("Reconciling stuck payouts");

        Instant cutoff = Instant.now().minus(10, ChronoUnit.MINUTES);
        List<PayoutRecord> stuckPayouts = payoutRepository.findStuckProcessingPayouts(cutoff);

        for (PayoutRecord payout : stuckPayouts) {
            try {
                reconcilePayout(payout);
            } catch (Exception e) {
                log.error("Failed to reconcile payout {}: {}", payout.getPayoutId(), e.getMessage());
            }
        }
    }

    private void reconcilePayout(PayoutRecord payout) {
        String txnId = payout.getGatewayTxnId() != null ? payout.getGatewayTxnId() : payout.getPayoutId();
        PaymentGatewayResponse status = paymentGateway.getTransactionStatus(txnId);

        if (status.isSuccess()) {
            // Payment completed, update our records
            payout.setStatus(PayoutStatus.COMPLETED);
            payout.setGatewayTxnId(status.getTransactionId());
            payout.setCompletedAt(Instant.now());
            payoutRepository.save(payout);
            log.warn("Reconciled payout {} as COMPLETED", payout.getPayoutId());
        } else if ("NOT_FOUND".equals(status.getErrorCode())) {
            // Payment was never submitted, reset for retry
            payout.setStatus(PayoutStatus.PENDING);
            payout.setProcessedAt(null);
            payout.setRetryCount(payout.getRetryCount() + 1);
            payoutRepository.save(payout);
            log.warn("Reset stuck payout {} to PENDING for retry", payout.getPayoutId());
        } else {
            // Mark as failed
            payout.setStatus(PayoutStatus.FAILED);
            payout.setErrorCode(status.getErrorCode());
            payout.setErrorMessage(status.getErrorMessage());
            payoutRepository.save(payout);
            log.error("Payout {} failed during reconciliation: {}", payout.getPayoutId(), status.getErrorCode());
        }
    }
}
```

---

## Kafka Consumer

```java
@Component
@Slf4j
public class OrderEventConsumer {

    private final BalanceService balanceService;
    private final OrderPayoutMappingRepository mappingRepository;
    private final AuditService auditService;

    @KafkaListener(topics = "${kafka.topics.order-events}", groupId = "${kafka.consumer.group-id}")
    public void consumeOrderEvent(ConsumerRecord<String, OrderEventRequest> record) {
        OrderEventRequest event = record.value();
        log.info("Received order event: {} for order {}", event.getEventType(), event.getOrderId());

        try {
            switch (event.getEventType()) {
                case ORDER_COMPLETED -> processOrderCompleted(event);
                case ORDER_CANCELLED -> processOrderCancelled(event);
                default -> log.warn("Unknown event type: {}", event.getEventType());
            }
        } catch (Exception e) {
            log.error("Failed to process order event {}: {}", event.getOrderId(), e.getMessage());
            throw e; // Will trigger retry or DLQ
        }
    }

    @Transactional
    private void processOrderCompleted(OrderEventRequest event) {
        for (ProductInfo product : event.getProducts()) {
            String sellerId = product.getSellerId();

            // Idempotency check
            if (mappingRepository.existsByOrderIdAndSellerId(event.getOrderId(), sellerId)) {
                log.info("Order {} already processed for seller {}, skipping", event.getOrderId(), sellerId);
                continue;
            }

            BigDecimal sellerAmount = product.getSellerPrice()
                .multiply(BigDecimal.valueOf(product.getQuantity()));

            // Credit balance
            balanceService.creditPendingBalance(sellerId, sellerAmount, event.getOrderId());

            // Create mapping
            OrderPayoutMapping mapping = OrderPayoutMapping.builder()
                .orderId(event.getOrderId())
                .sellerId(sellerId)
                .sellerAmount(sellerAmount)
                .status(MappingStatus.PENDING)
                .orderTimestamp(event.getOrderTimestamp())
                .build();
            mappingRepository.save(mapping);

            // Audit log
            auditService.logBalanceCredited(sellerId, sellerAmount, event.getOrderId());

            log.info("Credited {} to seller {} for order {}", sellerAmount, sellerId, event.getOrderId());
        }
    }

    @Transactional
    private void processOrderCancelled(OrderEventRequest event) {
        for (ProductInfo product : event.getProducts()) {
            balanceService.processOrderCancellation(event.getOrderId(), product.getSellerId());
        }
    }
}
```

---

## Configuration Files

### application.yml

```yaml
spring:
  application:
    name: seller-payment-system

  datasource:
    url: jdbc:postgresql://${DB_HOST:localhost}:${DB_PORT:5432}/${DB_NAME:payments}
    username: ${DB_USER:postgres}
    password: ${DB_PASSWORD:postgres}
    hikari:
      maximum-pool-size: 20
      minimum-idle: 5
      idle-timeout: 300000
      connection-timeout: 20000
      max-lifetime: 1200000

  jpa:
    hibernate:
      ddl-auto: validate
    properties:
      hibernate:
        dialect: org.hibernate.dialect.PostgreSQLDialect
        format_sql: true
    show-sql: false

  flyway:
    enabled: true
    locations: classpath:db/migration

  data:
    redis:
      host: ${REDIS_HOST:localhost}
      port: ${REDIS_PORT:6379}

  kafka:
    bootstrap-servers: ${KAFKA_BOOTSTRAP_SERVERS:localhost:9092}
    consumer:
      group-id: seller-payment-consumer
      auto-offset-reset: earliest
      key-deserializer: org.apache.kafka.common.serialization.StringDeserializer
      value-deserializer: org.springframework.kafka.support.serializer.JsonDeserializer
      properties:
        spring.json.trusted.packages: com.ecommerce.sellerpayment.dto
    producer:
      key-serializer: org.apache.kafka.common.serialization.StringSerializer
      value-serializer: org.springframework.kafka.support.serializer.JsonSerializer

kafka:
  topics:
    order-events: order-events
    payout-requests: payout-requests
    payout-dlq: payout-dlq

payment:
  gateway:
    url: ${GATEWAY_URL:https://gateway.example.com}
    api-key: ${GATEWAY_API_KEY}
    timeout-seconds: 120
    max-retries: 5

  settlement:
    window-days: 7

  payout:
    minimum-amount: 10.00
    max-retry-count: 5

server:
  port: 8080

management:
  endpoints:
    web:
      exposure:
        include: health,info,metrics,prometheus
  endpoint:
    health:
      show-details: always

logging:
  level:
    com.ecommerce.sellerpayment: INFO
    org.springframework.kafka: WARN
```

---

## Exception Handling

```java
@RestControllerAdvice
@Slf4j
public class GlobalExceptionHandler {

    @ExceptionHandler(InsufficientBalanceException.class)
    public ResponseEntity<ApiErrorResponse> handleInsufficientBalance(InsufficientBalanceException ex) {
        return ResponseEntity.badRequest().body(
            ApiErrorResponse.builder()
                .code("INSUFFICIENT_BALANCE")
                .message(ex.getMessage())
                .timestamp(Instant.now())
                .build()
        );
    }

    @ExceptionHandler(PayoutInProgressException.class)
    public ResponseEntity<ApiErrorResponse> handlePayoutInProgress(PayoutInProgressException ex) {
        return ResponseEntity.status(HttpStatus.CONFLICT).body(
            ApiErrorResponse.builder()
                .code("PAYOUT_IN_PROGRESS")
                .message(ex.getMessage())
                .timestamp(Instant.now())
                .build()
        );
    }

    @ExceptionHandler(SellerNotFoundException.class)
    public ResponseEntity<ApiErrorResponse> handleSellerNotFound(SellerNotFoundException ex) {
        return ResponseEntity.status(HttpStatus.NOT_FOUND).body(
            ApiErrorResponse.builder()
                .code("SELLER_NOT_FOUND")
                .message(ex.getMessage())
                .timestamp(Instant.now())
                .build()
        );
    }

    @ExceptionHandler(PayoutNotFoundException.class)
    public ResponseEntity<ApiErrorResponse> handlePayoutNotFound(PayoutNotFoundException ex) {
        return ResponseEntity.status(HttpStatus.NOT_FOUND).body(
            ApiErrorResponse.builder()
                .code("PAYOUT_NOT_FOUND")
                .message(ex.getMessage())
                .timestamp(Instant.now())
                .build()
        );
    }

    @ExceptionHandler(GatewayException.class)
    public ResponseEntity<ApiErrorResponse> handleGatewayException(GatewayException ex) {
        return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE).body(
            ApiErrorResponse.builder()
                .code("GATEWAY_UNAVAILABLE")
                .message(ex.getMessage())
                .timestamp(Instant.now())
                .build()
        );
    }

    @ExceptionHandler(OptimisticLockingFailureException.class)
    public ResponseEntity<ApiErrorResponse> handleOptimisticLocking(OptimisticLockingFailureException ex) {
        return ResponseEntity.status(HttpStatus.CONFLICT).body(
            ApiErrorResponse.builder()
                .code("CONCURRENT_MODIFICATION")
                .message("Resource was modified by another request, please retry")
                .timestamp(Instant.now())
                .build()
        );
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ApiErrorResponse> handleValidation(MethodArgumentNotValidException ex) {
        String errors = ex.getBindingResult().getFieldErrors().stream()
            .map(e -> e.getField() + ": " + e.getDefaultMessage())
            .collect(Collectors.joining(", "));

        return ResponseEntity.badRequest().body(
            ApiErrorResponse.builder()
                .code("VALIDATION_ERROR")
                .message(errors)
                .timestamp(Instant.now())
                .build()
        );
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ApiErrorResponse> handleGeneral(Exception ex) {
        log.error("Unexpected error", ex);
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(
            ApiErrorResponse.builder()
                .code("INTERNAL_ERROR")
                .message("An unexpected error occurred")
                .timestamp(Instant.now())
                .build()
        );
    }
}
```

---

## Docker Compose for Local Development

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: payments
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7
    ports:
      - "6379:6379"

  zookeeper:
    image: confluentinc/cp-zookeeper:7.4.0
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181

  kafka:
    image: confluentinc/cp-kafka:7.4.0
    depends_on:
      - zookeeper
    ports:
      - "9092:9092"
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1

volumes:
  postgres_data:
```

---

## Testing Requirements

### Unit Tests

1. **BalanceServiceTest**: Test balance operations, optimistic locking, cancellation handling
2. **PaymentProcessorServiceTest**: Test payout processing, retry logic, gateway interactions
3. **PayoutSchedulerServiceTest**: Test eligibility determination, idempotency

### Integration Tests

1. **PaymentFlowIntegrationTest**: End-to-end test from order event to payout completion
2. Use Testcontainers for PostgreSQL and Kafka
3. Mock the payment gateway

### Test Scenarios to Cover

- [ ] Order completion credits pending balance
- [ ] Settlement window moves pending to available
- [ ] Payout deducts available balance
- [ ] Order cancellation during pending state
- [ ] Order cancellation after settlement
- [ ] Gateway failure and retry
- [ ] Circuit breaker activation
- [ ] Concurrent payout prevention
- [ ] Optimistic locking on balance updates
- [ ] Idempotent order processing

---

## Implementation Notes for Agent

1. **Start with entities and repositories** - These form the foundation
2. **Implement services in order**: BalanceService → AuditService → PaymentProcessorService → PayoutSchedulerService
3. **Use @Transactional appropriately** - Especially for balance operations
4. **Implement circuit breaker** for gateway calls using Resilience4j or custom implementation
5. **Use Redis distributed locks** for scheduler leader election
6. **Generate unique IDs** using format: `PO-{date}-{sellerId}-{hash}`
7. **Handle timezone correctly** - Use Instant for all timestamps
8. **Implement proper logging** at INFO level for business events, ERROR for failures
9. **Add OpenAPI annotations** to all controller methods
10. **Use MapStruct** for DTO-Entity mapping if needed

---

## API Response Format Standard

All responses should follow this structure:

**Success Response**:
```json
{
  "data": { ... },
  "timestamp": "2026-01-06T14:30:00Z"
}
```

**Error Response**:
```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message",
    "details": { ... }
  },
  "timestamp": "2026-01-06T14:30:00Z",
  "traceId": "abc123"
}
```

---

## Acceptance Criteria

The implementation is complete when:

1. All entities are created with proper JPA annotations
2. All repositories have the specified query methods
3. All services implement the business logic as specified
4. All REST endpoints are functional and documented
5. Scheduled jobs run on the specified intervals
6. Kafka consumer processes order events correctly
7. Payment gateway integration works with mock implementation
8. Audit logging captures all specified events
9. Exception handling returns proper error responses
10. Unit tests cover critical paths
11. Application starts successfully with docker-compose dependencies

