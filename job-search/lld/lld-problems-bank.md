# LLD Problems Bank

> Collection of common LLD problems with approach notes

---

## Problem Categories

| Category | Problems |
|----------|----------|
| Data Structures | LRU Cache, LFU Cache, Consistent Hashing |
| E-commerce | Shopping Cart, Inventory, Order Management |
| Booking | Parking Lot, Movie Tickets, Meeting Scheduler |
| Social | Chat System, Feed, Notification Service |
| Gaming | Chess, Tic-Tac-Toe, Snake & Ladder |
| Infra | Rate Limiter, Logger, Task Scheduler |
| Payments | Payment Gateway, Wallet, Split Bill |

---

## 1. URL Shortener (LLD Focus)

### Requirements
- Generate short URLs from long URLs
- Redirect short URL to original
- Custom aliases optional
- Expiration support
- Click analytics

### Core Classes

```java
class URLShortenerService {
    private URLRepository repository;
    private IDGenerator idGenerator;
    private Cache<String, URL> cache;

    public ShortURL shorten(String longUrl, String customAlias, Duration expiry) {
        String shortCode = customAlias != null ?
            validateAndUseCustom(customAlias) :
            idGenerator.generate();

        URL url = URL.builder()
            .shortCode(shortCode)
            .longUrl(longUrl)
            .createdAt(Instant.now())
            .expiresAt(Instant.now().plus(expiry))
            .build();

        repository.save(url);
        return new ShortURL(BASE_URL + shortCode);
    }

    public String resolve(String shortCode) {
        URL url = cache.get(shortCode, () -> repository.findByShortCode(shortCode));

        if (url == null || url.isExpired()) {
            throw new URLNotFoundException();
        }

        // Async analytics
        analyticsService.recordClick(shortCode);

        return url.getLongUrl();
    }
}

interface IDGenerator {
    String generate();
}

class Base62Generator implements IDGenerator {
    private AtomicLong counter;

    public String generate() {
        return Base62.encode(counter.incrementAndGet());
    }
}

class URL {
    private String shortCode;
    private String longUrl;
    private Instant createdAt;
    private Instant expiresAt;
    private long clickCount;

    boolean isExpired() {
        return expiresAt != null && Instant.now().isAfter(expiresAt);
    }
}
```

---

## 2. File System

### Requirements
- Support files and directories
- CRUD operations
- Path navigation
- Search functionality

### Core Classes

```java
// Composite pattern for files and directories
abstract class FileSystemEntity {
    protected String name;
    protected Directory parent;
    protected Instant createdAt;
    protected Instant modifiedAt;

    abstract long getSize();
    abstract void display(int indent);

    String getPath() {
        if (parent == null) return "/" + name;
        return parent.getPath() + "/" + name;
    }
}

class File extends FileSystemEntity {
    private byte[] content;

    long getSize() { return content.length; }

    void display(int indent) {
        System.out.println(" ".repeat(indent) + name);
    }
}

class Directory extends FileSystemEntity {
    private Map<String, FileSystemEntity> children = new HashMap<>();

    void add(FileSystemEntity entity) {
        entity.parent = this;
        children.put(entity.name, entity);
    }

    void remove(String name) {
        children.remove(name);
    }

    FileSystemEntity get(String name) {
        return children.get(name);
    }

    long getSize() {
        return children.values().stream()
            .mapToLong(FileSystemEntity::getSize)
            .sum();
    }

    void display(int indent) {
        System.out.println(" ".repeat(indent) + name + "/");
        children.values().forEach(c -> c.display(indent + 2));
    }
}

class FileSystem {
    private Directory root = new Directory("root");
    private Directory current = root;

    void mkdir(String name) {
        current.add(new Directory(name));
    }

    void touch(String name) {
        current.add(new File(name));
    }

    void cd(String path) {
        if (path.equals("..")) {
            if (current.parent != null) current = current.parent;
        } else {
            FileSystemEntity entity = current.get(path);
            if (entity instanceof Directory) {
                current = (Directory) entity;
            }
        }
    }

    List<FileSystemEntity> ls() {
        return new ArrayList<>(current.children.values());
    }

    List<File> search(String pattern) {
        return searchRecursive(root, pattern);
    }

    private List<File> searchRecursive(Directory dir, String pattern) {
        List<File> results = new ArrayList<>();
        for (FileSystemEntity entity : dir.children.values()) {
            if (entity instanceof File && entity.name.matches(pattern)) {
                results.add((File) entity);
            } else if (entity instanceof Directory) {
                results.addAll(searchRecursive((Directory) entity, pattern));
            }
        }
        return results;
    }
}
```

---

## 3. Hotel Booking System

### Requirements
- Multiple room types
- Date-based availability
- Booking with payment
- Cancellation policy

### Core Classes

```java
enum RoomType { SINGLE, DOUBLE, DELUXE, SUITE }
enum BookingStatus { PENDING, CONFIRMED, CANCELLED, COMPLETED }

class Room {
    private String roomNumber;
    private RoomType type;
    private BigDecimal pricePerNight;
    private Set<LocalDate> bookedDates = new HashSet<>();

    boolean isAvailable(LocalDate checkIn, LocalDate checkOut) {
        return checkIn.datesUntil(checkOut)
            .noneMatch(bookedDates::contains);
    }

    void book(LocalDate checkIn, LocalDate checkOut) {
        checkIn.datesUntil(checkOut).forEach(bookedDates::add);
    }

    void release(LocalDate checkIn, LocalDate checkOut) {
        checkIn.datesUntil(checkOut).forEach(bookedDates::remove);
    }
}

class Booking {
    private String bookingId;
    private Guest guest;
    private Room room;
    private LocalDate checkIn;
    private LocalDate checkOut;
    private BigDecimal totalAmount;
    private BookingStatus status;
    private LocalDateTime createdAt;

    BigDecimal calculateTotal() {
        long nights = ChronoUnit.DAYS.between(checkIn, checkOut);
        return room.getPricePerNight().multiply(BigDecimal.valueOf(nights));
    }

    boolean isCancellable() {
        return status == BookingStatus.CONFIRMED &&
               LocalDate.now().isBefore(checkIn.minusDays(1));
    }
}

class Hotel {
    private String name;
    private List<Room> rooms = new ArrayList<>();
    private List<Booking> bookings = new ArrayList<>();

    List<Room> searchAvailableRooms(RoomType type, LocalDate checkIn, LocalDate checkOut) {
        return rooms.stream()
            .filter(r -> r.getType() == type)
            .filter(r -> r.isAvailable(checkIn, checkOut))
            .collect(Collectors.toList());
    }
}

class BookingService {
    private Hotel hotel;
    private PaymentService paymentService;
    private NotificationService notificationService;

    public Booking createBooking(Guest guest, RoomType type,
                                  LocalDate checkIn, LocalDate checkOut) {
        // Find available room
        List<Room> available = hotel.searchAvailableRooms(type, checkIn, checkOut);
        if (available.isEmpty()) {
            throw new NoRoomAvailableException();
        }

        Room room = available.get(0);

        // Create booking
        Booking booking = new Booking(guest, room, checkIn, checkOut);
        booking.setStatus(BookingStatus.PENDING);

        // Process payment
        PaymentResult result = paymentService.process(
            booking.calculateTotal(), guest.getPaymentMethod());

        if (result.isSuccess()) {
            room.book(checkIn, checkOut);
            booking.setStatus(BookingStatus.CONFIRMED);
            notificationService.sendConfirmation(booking);
        } else {
            booking.setStatus(BookingStatus.CANCELLED);
            throw new PaymentFailedException();
        }

        return booking;
    }

    public void cancelBooking(String bookingId) {
        Booking booking = findBooking(bookingId);

        if (!booking.isCancellable()) {
            throw new CancellationNotAllowedException();
        }

        // Calculate refund based on policy
        BigDecimal refund = calculateRefund(booking);

        // Process refund
        paymentService.refund(booking.getPaymentId(), refund);

        // Release room
        booking.getRoom().release(booking.getCheckIn(), booking.getCheckOut());
        booking.setStatus(BookingStatus.CANCELLED);

        notificationService.sendCancellationConfirmation(booking);
    }
}
```

---

## 4. Elevator System

### Requirements
- Multiple elevators
- Efficient scheduling
- Handle concurrent requests
- Emergency handling

### Core Classes

```java
enum Direction { UP, DOWN, IDLE }
enum ElevatorStatus { MOVING, STOPPED, MAINTENANCE }

class Elevator {
    private int id;
    private int currentFloor;
    private Direction direction;
    private ElevatorStatus status;
    private PriorityQueue<Integer> upQueue;    // Min heap
    private PriorityQueue<Integer> downQueue;  // Max heap
    private int capacity;
    private int currentLoad;

    void addDestination(int floor) {
        if (floor > currentFloor) {
            upQueue.add(floor);
        } else if (floor < currentFloor) {
            downQueue.add(floor);
        }
    }

    void move() {
        if (direction == Direction.UP && !upQueue.isEmpty()) {
            currentFloor = upQueue.poll();
        } else if (direction == Direction.DOWN && !downQueue.isEmpty()) {
            currentFloor = downQueue.poll();
        } else {
            // Switch direction or go idle
            if (!upQueue.isEmpty()) {
                direction = Direction.UP;
            } else if (!downQueue.isEmpty()) {
                direction = Direction.DOWN;
            } else {
                direction = Direction.IDLE;
            }
        }
    }

    int distanceTo(int floor, Direction requestDir) {
        if (direction == Direction.IDLE) {
            return Math.abs(floor - currentFloor);
        }

        if (direction == requestDir) {
            if (direction == Direction.UP && floor >= currentFloor) {
                return floor - currentFloor;
            }
            if (direction == Direction.DOWN && floor <= currentFloor) {
                return currentFloor - floor;
            }
        }

        // Elevator going opposite direction, needs to come back
        return Integer.MAX_VALUE; // Simplified
    }
}

class ElevatorController {
    private List<Elevator> elevators;

    void requestElevator(int floor, Direction direction) {
        Elevator best = findBestElevator(floor, direction);
        best.addDestination(floor);
    }

    private Elevator findBestElevator(int floor, Direction direction) {
        return elevators.stream()
            .filter(e -> e.getStatus() != ElevatorStatus.MAINTENANCE)
            .min(Comparator.comparingInt(e -> e.distanceTo(floor, direction)))
            .orElseThrow();
    }

    void selectFloor(int elevatorId, int floor) {
        Elevator elevator = findElevator(elevatorId);
        elevator.addDestination(floor);
    }

    void step() {
        elevators.forEach(Elevator::move);
    }
}
```

---

## 5. Splitwise / Expense Sharing

### Requirements
- Add expenses split among users
- Multiple split types (equal, exact, percentage)
- Show balances
- Simplify debts

### Core Classes

```java
enum SplitType { EQUAL, EXACT, PERCENTAGE }

abstract class Split {
    protected User user;
    protected BigDecimal amount;

    abstract void validate(BigDecimal totalAmount, List<Split> splits);
}

class EqualSplit extends Split {
    void validate(BigDecimal totalAmount, List<Split> splits) {
        this.amount = totalAmount.divide(BigDecimal.valueOf(splits.size()), RoundingMode.CEILING);
    }
}

class ExactSplit extends Split {
    void validate(BigDecimal totalAmount, List<Split> splits) {
        BigDecimal sum = splits.stream()
            .map(s -> s.amount)
            .reduce(BigDecimal.ZERO, BigDecimal::add);
        if (!sum.equals(totalAmount)) {
            throw new InvalidSplitException("Exact amounts don't add up");
        }
    }
}

class PercentageSplit extends Split {
    private double percentage;

    void validate(BigDecimal totalAmount, List<Split> splits) {
        double totalPercent = splits.stream()
            .mapToDouble(s -> ((PercentageSplit) s).percentage)
            .sum();
        if (totalPercent != 100) {
            throw new InvalidSplitException("Percentages must sum to 100");
        }
        this.amount = totalAmount.multiply(BigDecimal.valueOf(percentage / 100));
    }
}

class Expense {
    private String id;
    private User paidBy;
    private BigDecimal amount;
    private String description;
    private List<Split> splits;
    private LocalDateTime createdAt;
}

class ExpenseService {
    private Map<String, User> users = new HashMap<>();
    private List<Expense> expenses = new ArrayList<>();
    // Balance map: user -> (otherUser -> amount owed)
    private Map<String, Map<String, BigDecimal>> balances = new HashMap<>();

    void addExpense(String paidById, BigDecimal amount,
                    List<Split> splits, String description) {
        User paidBy = users.get(paidById);

        // Validate splits
        splits.get(0).validate(amount, splits);

        // Create expense
        Expense expense = new Expense(paidBy, amount, splits, description);
        expenses.add(expense);

        // Update balances
        for (Split split : splits) {
            if (!split.user.equals(paidBy)) {
                // split.user owes paidBy
                updateBalance(split.user.getId(), paidById, split.amount);
            }
        }
    }

    private void updateBalance(String from, String to, BigDecimal amount) {
        balances.computeIfAbsent(from, k -> new HashMap<>())
            .merge(to, amount, BigDecimal::add);

        // Also update reverse (negative)
        balances.computeIfAbsent(to, k -> new HashMap<>())
            .merge(from, amount.negate(), BigDecimal::add);
    }

    Map<String, BigDecimal> getBalance(String userId) {
        return balances.getOrDefault(userId, Collections.emptyMap())
            .entrySet().stream()
            .filter(e -> e.getValue().compareTo(BigDecimal.ZERO) != 0)
            .collect(Collectors.toMap(Map.Entry::getKey, Map.Entry::getValue));
    }

    List<Settlement> simplifyDebts() {
        // Calculate net balance per user
        Map<String, BigDecimal> netBalances = new HashMap<>();
        for (Map.Entry<String, Map<String, BigDecimal>> entry : balances.entrySet()) {
            BigDecimal net = entry.getValue().values().stream()
                .reduce(BigDecimal.ZERO, BigDecimal::add);
            netBalances.put(entry.getKey(), net);
        }

        // Greedy matching: match biggest creditor with biggest debtor
        PriorityQueue<Map.Entry<String, BigDecimal>> creditors =
            new PriorityQueue<>((a, b) -> b.getValue().compareTo(a.getValue()));
        PriorityQueue<Map.Entry<String, BigDecimal>> debtors =
            new PriorityQueue<>(Comparator.comparing(Map.Entry::getValue));

        for (Map.Entry<String, BigDecimal> entry : netBalances.entrySet()) {
            if (entry.getValue().compareTo(BigDecimal.ZERO) > 0) {
                creditors.add(entry);
            } else if (entry.getValue().compareTo(BigDecimal.ZERO) < 0) {
                debtors.add(entry);
            }
        }

        List<Settlement> settlements = new ArrayList<>();
        while (!creditors.isEmpty() && !debtors.isEmpty()) {
            // Match and create settlement
            // ... implementation
        }

        return settlements;
    }
}
```

---

## 6. Task Scheduler

### Requirements
- Schedule tasks at specific times
- Recurring tasks (daily, weekly)
- Priority-based execution
- Retry on failure

### Core Classes

```java
interface Task {
    void execute();
    String getId();
    Priority getPriority();
}

enum TaskStatus { PENDING, RUNNING, COMPLETED, FAILED }
enum RecurrenceType { NONE, DAILY, WEEKLY, MONTHLY }

class ScheduledTask {
    private Task task;
    private LocalDateTime scheduledTime;
    private RecurrenceType recurrence;
    private TaskStatus status;
    private int retryCount;
    private int maxRetries;

    LocalDateTime getNextRunTime() {
        if (recurrence == RecurrenceType.NONE) return null;
        return switch (recurrence) {
            case DAILY -> scheduledTime.plusDays(1);
            case WEEKLY -> scheduledTime.plusWeeks(1);
            case MONTHLY -> scheduledTime.plusMonths(1);
            default -> null;
        };
    }
}

class TaskScheduler {
    // Priority queue ordered by scheduled time, then priority
    private PriorityQueue<ScheduledTask> taskQueue = new PriorityQueue<>(
        Comparator.comparing(ScheduledTask::getScheduledTime)
                  .thenComparing(t -> t.getTask().getPriority())
    );
    private ExecutorService executor;
    private ScheduledExecutorService scheduler;

    void schedule(Task task, LocalDateTime time, RecurrenceType recurrence) {
        ScheduledTask scheduledTask = new ScheduledTask(task, time, recurrence);
        taskQueue.add(scheduledTask);
    }

    void start() {
        scheduler.scheduleAtFixedRate(this::processQueue, 0, 1, TimeUnit.SECONDS);
    }

    private void processQueue() {
        LocalDateTime now = LocalDateTime.now();

        while (!taskQueue.isEmpty() &&
               !taskQueue.peek().getScheduledTime().isAfter(now)) {

            ScheduledTask scheduledTask = taskQueue.poll();
            executor.submit(() -> executeTask(scheduledTask));
        }
    }

    private void executeTask(ScheduledTask scheduledTask) {
        try {
            scheduledTask.setStatus(TaskStatus.RUNNING);
            scheduledTask.getTask().execute();
            scheduledTask.setStatus(TaskStatus.COMPLETED);

            // Schedule next occurrence
            if (scheduledTask.getRecurrence() != RecurrenceType.NONE) {
                ScheduledTask next = scheduledTask.createNext();
                taskQueue.add(next);
            }
        } catch (Exception e) {
            handleFailure(scheduledTask, e);
        }
    }

    private void handleFailure(ScheduledTask task, Exception e) {
        if (task.getRetryCount() < task.getMaxRetries()) {
            task.incrementRetryCount();
            task.setScheduledTime(calculateRetryTime(task));
            task.setStatus(TaskStatus.PENDING);
            taskQueue.add(task);
        } else {
            task.setStatus(TaskStatus.FAILED);
            // Alert/log failure
        }
    }
}
```

---

## Quick Problem-Pattern Mapping

| Problem | Key Patterns |
|---------|--------------|
| Parking Lot | Strategy, Factory |
| LRU Cache | Composite (HashMap + DLL) |
| Rate Limiter | Strategy, Sliding Window |
| Notification | Observer, Strategy, Factory |
| File System | Composite |
| URL Shortener | Factory |
| Elevator | State, Strategy |
| Splitwise | Strategy (split types) |
| Task Scheduler | Priority Queue, Observer |
| Hotel Booking | Strategy, State |

---

## Practice Checklist

- [ ] LRU Cache
- [ ] Rate Limiter
- [ ] Parking Lot
- [ ] URL Shortener
- [ ] File System
- [ ] Notification Service
- [ ] Payment Gateway
- [ ] Hotel Booking
- [ ] Elevator System
- [ ] Splitwise
- [ ] Task Scheduler
- [ ] Chess Game
- [ ] Snake and Ladder

