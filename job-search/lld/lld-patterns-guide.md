# Low-Level Design (LLD) Interview Guide

> **Purpose**: Prepare for object-oriented design and LLD rounds
> **Focus**: Clean code, SOLID principles, design patterns, extensibility

---

## LLD vs HLD

| Aspect | High-Level Design (HLD) | Low-Level Design (LLD) |
|--------|------------------------|------------------------|
| Focus | System components, data flow | Classes, interfaces, methods |
| Scope | Distributed systems | Single service/module |
| Output | Architecture diagrams | Class diagrams, code |
| Time | 45-60 min | 45-60 min |
| Evaluation | Scalability, trade-offs | OOP, patterns, extensibility |

---

## LLD Interview Framework

### Step 1: Clarify Requirements (5 min)
- What are the core features?
- What's the expected scale?
- Any specific constraints?
- Are we designing API or just classes?

### Step 2: Identify Core Entities (5 min)
- List the main nouns from requirements
- Identify relationships between entities
- Note which entities have behavior

### Step 3: Design Class Diagram (15 min)
- Classes with attributes
- Methods (public interface)
- Relationships (has-a, is-a)
- Interfaces for extensibility

### Step 4: Implement Key Classes (15-20 min)
- Start with main orchestrator
- Implement core business logic
- Show interface implementations
- Handle edge cases

### Step 5: Discuss Improvements (5 min)
- Design patterns applied
- Future extensibility
- Performance considerations

---

## SOLID Principles Quick Reference

### S - Single Responsibility
```java
// BAD: One class doing too much
class UserService {
    void createUser() { }
    void sendEmail() { }
    void generateReport() { }
}

// GOOD: Separate responsibilities
class UserService { void createUser() { } }
class EmailService { void sendEmail() { } }
class ReportService { void generateReport() { } }
```

### O - Open/Closed
```java
// BAD: Modifying existing code for new payment types
class PaymentProcessor {
    void process(String type) {
        if (type.equals("CREDIT")) { ... }
        else if (type.equals("DEBIT")) { ... }
        // Need to modify this for new types!
    }
}

// GOOD: Extend without modifying
interface PaymentStrategy { void process(); }
class CreditPayment implements PaymentStrategy { }
class DebitPayment implements PaymentStrategy { }
// New payment type = new class, no modification
```

### L - Liskov Substitution
```java
// BAD: Subclass changes parent behavior
class Rectangle {
    void setWidth(int w) { }
    void setHeight(int h) { }
}
class Square extends Rectangle {
    // Violates LSP - can't substitute Square for Rectangle
}

// GOOD: Use composition or separate hierarchy
interface Shape { int getArea(); }
class Rectangle implements Shape { }
class Square implements Shape { }
```

### I - Interface Segregation
```java
// BAD: Fat interface
interface Worker {
    void work();
    void eat();
    void sleep();
}

// GOOD: Segregated interfaces
interface Workable { void work(); }
interface Eatable { void eat(); }
class Robot implements Workable { }
class Human implements Workable, Eatable { }
```

### D - Dependency Inversion
```java
// BAD: High-level depends on low-level
class OrderService {
    private MySQLDatabase db = new MySQLDatabase();
}

// GOOD: Depend on abstractions
class OrderService {
    private Database db;
    OrderService(Database db) { this.db = db; }
}
interface Database { void save(); }
class MySQLDatabase implements Database { }
class PostgresDatabase implements Database { }
```

---

## Essential Design Patterns

### 1. Strategy Pattern
**Use when**: Multiple algorithms for same operation

```java
interface PricingStrategy {
    double calculatePrice(Order order);
}

class RegularPricing implements PricingStrategy {
    public double calculatePrice(Order order) {
        return order.getSubtotal();
    }
}

class PremiumPricing implements PricingStrategy {
    public double calculatePrice(Order order) {
        return order.getSubtotal() * 0.9; // 10% discount
    }
}

class OrderService {
    private PricingStrategy pricingStrategy;

    public void setPricingStrategy(PricingStrategy strategy) {
        this.pricingStrategy = strategy;
    }

    public double checkout(Order order) {
        return pricingStrategy.calculatePrice(order);
    }
}
```

### 2. Factory Pattern
**Use when**: Object creation logic is complex

```java
interface Notification { void send(String message); }

class EmailNotification implements Notification { ... }
class SMSNotification implements Notification { ... }
class PushNotification implements Notification { ... }

class NotificationFactory {
    public static Notification create(String type) {
        switch (type) {
            case "EMAIL": return new EmailNotification();
            case "SMS": return new SMSNotification();
            case "PUSH": return new PushNotification();
            default: throw new IllegalArgumentException();
        }
    }
}
```

### 3. Observer Pattern
**Use when**: Objects need to react to state changes

```java
interface Observer {
    void update(Event event);
}

interface Subject {
    void addObserver(Observer o);
    void removeObserver(Observer o);
    void notifyObservers(Event event);
}

class OrderService implements Subject {
    private List<Observer> observers = new ArrayList<>();

    public void placeOrder(Order order) {
        // process order
        notifyObservers(new OrderPlacedEvent(order));
    }

    public void notifyObservers(Event event) {
        for (Observer o : observers) {
            o.update(event);
        }
    }
}

class InventoryService implements Observer {
    public void update(Event event) {
        if (event instanceof OrderPlacedEvent) {
            // reduce inventory
        }
    }
}
```

### 4. Singleton Pattern
**Use when**: Exactly one instance needed (use sparingly!)

```java
class ConfigManager {
    private static ConfigManager instance;
    private Properties config;

    private ConfigManager() {
        // load config
    }

    public static synchronized ConfigManager getInstance() {
        if (instance == null) {
            instance = new ConfigManager();
        }
        return instance;
    }
}
```

### 5. Builder Pattern
**Use when**: Complex object construction

```java
class Order {
    private String customerId;
    private List<Item> items;
    private Address shippingAddress;
    private PaymentMethod payment;

    private Order(Builder builder) {
        this.customerId = builder.customerId;
        this.items = builder.items;
        // ...
    }

    public static class Builder {
        private String customerId;
        private List<Item> items = new ArrayList<>();

        public Builder customerId(String id) {
            this.customerId = id;
            return this;
        }

        public Builder addItem(Item item) {
            this.items.add(item);
            return this;
        }

        public Order build() {
            // validate
            return new Order(this);
        }
    }
}

// Usage
Order order = new Order.Builder()
    .customerId("123")
    .addItem(item1)
    .addItem(item2)
    .build();
```

### 6. State Pattern
**Use when**: Object behavior changes based on state

```java
interface OrderState {
    void next(Order order);
    void cancel(Order order);
}

class PendingState implements OrderState {
    public void next(Order order) {
        order.setState(new ConfirmedState());
    }
    public void cancel(Order order) {
        order.setState(new CancelledState());
    }
}

class ConfirmedState implements OrderState {
    public void next(Order order) {
        order.setState(new ShippedState());
    }
    public void cancel(Order order) {
        // Cannot cancel confirmed order
        throw new IllegalStateException();
    }
}

class Order {
    private OrderState state = new PendingState();

    public void setState(OrderState state) {
        this.state = state;
    }

    public void next() { state.next(this); }
    public void cancel() { state.cancel(this); }
}
```

---

## Common LLD Problems

### 1. Rate Limiter

**Requirements:**
- Limit requests per user/IP
- Multiple algorithms (token bucket, sliding window)
- Distributed support

```java
interface RateLimiter {
    boolean allowRequest(String clientId);
}

class TokenBucketRateLimiter implements RateLimiter {
    private final int maxTokens;
    private final int refillRate; // tokens per second
    private final Map<String, Bucket> buckets = new ConcurrentHashMap<>();

    public boolean allowRequest(String clientId) {
        Bucket bucket = buckets.computeIfAbsent(clientId,
            k -> new Bucket(maxTokens, refillRate));
        return bucket.tryConsume();
    }
}

class Bucket {
    private int tokens;
    private long lastRefillTime;
    private final int maxTokens;
    private final int refillRate;

    synchronized boolean tryConsume() {
        refill();
        if (tokens > 0) {
            tokens--;
            return true;
        }
        return false;
    }

    private void refill() {
        long now = System.currentTimeMillis();
        int tokensToAdd = (int)((now - lastRefillTime) / 1000) * refillRate;
        tokens = Math.min(maxTokens, tokens + tokensToAdd);
        lastRefillTime = now;
    }
}
```

---

### 2. Parking Lot System

**Requirements:**
- Multiple floors, multiple spot types
- Vehicle types: motorcycle, car, truck
- Entry/exit tracking, billing

```java
// Enums
enum VehicleType { MOTORCYCLE, CAR, TRUCK }
enum SpotType { COMPACT, REGULAR, LARGE }

// Core Entities
abstract class Vehicle {
    private String licensePlate;
    private VehicleType type;
    abstract SpotType getRequiredSpotType();
}

class Car extends Vehicle {
    SpotType getRequiredSpotType() { return SpotType.REGULAR; }
}

class ParkingSpot {
    private String spotId;
    private SpotType type;
    private Vehicle currentVehicle;
    private boolean isAvailable = true;

    boolean canFit(Vehicle vehicle) {
        return isAvailable && type.ordinal() >= vehicle.getRequiredSpotType().ordinal();
    }

    void park(Vehicle vehicle) {
        this.currentVehicle = vehicle;
        this.isAvailable = false;
    }

    void release() {
        this.currentVehicle = null;
        this.isAvailable = true;
    }
}

class ParkingFloor {
    private String floorId;
    private Map<SpotType, List<ParkingSpot>> spotsByType;

    ParkingSpot findAvailableSpot(VehicleType vehicleType) {
        SpotType required = getRequiredSpotType(vehicleType);
        return spotsByType.get(required).stream()
            .filter(ParkingSpot::isAvailable)
            .findFirst()
            .orElse(null);
    }
}

class ParkingLot {
    private List<ParkingFloor> floors;
    private Map<String, ParkingTicket> activeTickets;

    ParkingTicket parkVehicle(Vehicle vehicle) {
        for (ParkingFloor floor : floors) {
            ParkingSpot spot = floor.findAvailableSpot(vehicle.getType());
            if (spot != null) {
                spot.park(vehicle);
                ParkingTicket ticket = new ParkingTicket(vehicle, spot);
                activeTickets.put(ticket.getId(), ticket);
                return ticket;
            }
        }
        throw new ParkingFullException();
    }

    double exitVehicle(String ticketId) {
        ParkingTicket ticket = activeTickets.remove(ticketId);
        ticket.getSpot().release();
        return calculateFee(ticket);
    }
}
```

---

### 3. LRU Cache

**Requirements:**
- O(1) get and put operations
- Evict least recently used when capacity reached

```java
class LRUCache<K, V> {
    private final int capacity;
    private final Map<K, Node<K, V>> map;
    private final DoublyLinkedList<K, V> list;

    public LRUCache(int capacity) {
        this.capacity = capacity;
        this.map = new HashMap<>();
        this.list = new DoublyLinkedList<>();
    }

    public V get(K key) {
        if (!map.containsKey(key)) return null;
        Node<K, V> node = map.get(key);
        list.moveToHead(node);
        return node.value;
    }

    public void put(K key, V value) {
        if (map.containsKey(key)) {
            Node<K, V> node = map.get(key);
            node.value = value;
            list.moveToHead(node);
        } else {
            if (map.size() >= capacity) {
                Node<K, V> tail = list.removeTail();
                map.remove(tail.key);
            }
            Node<K, V> newNode = new Node<>(key, value);
            list.addToHead(newNode);
            map.put(key, newNode);
        }
    }
}

class Node<K, V> {
    K key;
    V value;
    Node<K, V> prev, next;
}

class DoublyLinkedList<K, V> {
    private Node<K, V> head, tail;

    void addToHead(Node<K, V> node) { ... }
    void moveToHead(Node<K, V> node) { ... }
    Node<K, V> removeTail() { ... }
}
```

---

### 4. Notification Service

**Requirements:**
- Multiple channels (email, SMS, push)
- Priority levels
- Retry logic
- Rate limiting

```java
// Strategy for different channels
interface NotificationChannel {
    void send(Notification notification);
    boolean supports(NotificationType type);
}

class EmailChannel implements NotificationChannel {
    private EmailClient emailClient;

    public void send(Notification notification) {
        emailClient.send(notification.getRecipient(),
                        notification.getSubject(),
                        notification.getBody());
    }

    public boolean supports(NotificationType type) {
        return type == NotificationType.EMAIL;
    }
}

class SMSChannel implements NotificationChannel { ... }
class PushChannel implements NotificationChannel { ... }

// Notification entity
class Notification {
    private String id;
    private String userId;
    private NotificationType type;
    private Priority priority;
    private String subject;
    private String body;
    private NotificationStatus status;
    private int retryCount;
    private LocalDateTime scheduledTime;
}

enum Priority { LOW, MEDIUM, HIGH, CRITICAL }
enum NotificationStatus { PENDING, SENT, FAILED, RETRYING }

// Main service
class NotificationService {
    private List<NotificationChannel> channels;
    private NotificationRepository repository;
    private RateLimiter rateLimiter;
    private RetryPolicy retryPolicy;

    public void send(Notification notification) {
        // Rate limit check
        if (!rateLimiter.allowRequest(notification.getUserId())) {
            throw new RateLimitExceededException();
        }

        // Find appropriate channel
        NotificationChannel channel = channels.stream()
            .filter(c -> c.supports(notification.getType()))
            .findFirst()
            .orElseThrow();

        try {
            channel.send(notification);
            notification.setStatus(NotificationStatus.SENT);
        } catch (Exception e) {
            handleFailure(notification, e);
        }

        repository.save(notification);
    }

    private void handleFailure(Notification notification, Exception e) {
        if (retryPolicy.shouldRetry(notification)) {
            notification.setStatus(NotificationStatus.RETRYING);
            notification.incrementRetryCount();
            scheduleRetry(notification);
        } else {
            notification.setStatus(NotificationStatus.FAILED);
        }
    }
}
```

---

### 5. Payment Gateway (LLD)

**Requirements:**
- Multiple payment methods
- Transaction state management
- Idempotency
- Refund support

```java
// Payment method abstraction
interface PaymentMethod {
    PaymentResult process(PaymentRequest request);
    PaymentResult refund(RefundRequest request);
}

class CreditCardPayment implements PaymentMethod { ... }
class UPIPayment implements PaymentMethod { ... }
class WalletPayment implements PaymentMethod { ... }

// Transaction entity
class Transaction {
    private String transactionId;
    private String orderId;
    private String idempotencyKey;
    private BigDecimal amount;
    private Currency currency;
    private PaymentMethodType methodType;
    private TransactionStatus status;
    private List<TransactionEvent> events;

    void transition(TransactionStatus newStatus) {
        // Validate state transition
        if (!isValidTransition(this.status, newStatus)) {
            throw new InvalidStateTransitionException();
        }
        this.status = newStatus;
        events.add(new TransactionEvent(newStatus, LocalDateTime.now()));
    }
}

enum TransactionStatus {
    CREATED, PROCESSING, COMPLETED, FAILED, REFUND_PENDING, REFUNDED
}

// Main service
class PaymentService {
    private Map<PaymentMethodType, PaymentMethod> paymentMethods;
    private TransactionRepository repository;
    private IdempotencyStore idempotencyStore;

    public Transaction processPayment(PaymentRequest request) {
        // Idempotency check
        String idempotencyKey = request.getIdempotencyKey();
        Transaction existing = idempotencyStore.get(idempotencyKey);
        if (existing != null) {
            return existing;
        }

        // Create transaction
        Transaction transaction = new Transaction(request);
        transaction.transition(TransactionStatus.PROCESSING);

        // Process via appropriate method
        PaymentMethod method = paymentMethods.get(request.getMethodType());
        PaymentResult result = method.process(request);

        // Update status based on result
        if (result.isSuccess()) {
            transaction.transition(TransactionStatus.COMPLETED);
        } else {
            transaction.transition(TransactionStatus.FAILED);
        }

        // Store with idempotency key
        repository.save(transaction);
        idempotencyStore.put(idempotencyKey, transaction);

        return transaction;
    }

    public Transaction refund(RefundRequest request) {
        Transaction original = repository.findById(request.getTransactionId());

        if (original.getStatus() != TransactionStatus.COMPLETED) {
            throw new InvalidRefundException();
        }

        original.transition(TransactionStatus.REFUND_PENDING);

        PaymentMethod method = paymentMethods.get(original.getMethodType());
        PaymentResult result = method.refund(request);

        if (result.isSuccess()) {
            original.transition(TransactionStatus.REFUNDED);
        } else {
            original.transition(TransactionStatus.COMPLETED); // Rollback
        }

        return repository.save(original);
    }
}
```

---

## LLD Interview Checklist

### Before Starting
- [ ] Clarified all requirements
- [ ] Identified main entities
- [ ] Understood scale expectations

### During Design
- [ ] Used appropriate design patterns
- [ ] Applied SOLID principles
- [ ] Kept interfaces clean and focused
- [ ] Handled edge cases

### Code Quality
- [ ] Meaningful class/method names
- [ ] Single responsibility per class
- [ ] Immutability where appropriate
- [ ] Thread safety considerations

### After Design
- [ ] Explained trade-offs
- [ ] Discussed extensibility
- [ ] Mentioned testing approach

