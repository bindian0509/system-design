package com.clearinghouse.model;

import java.util.Objects;

/**
 * Represents a participant bank in the clearing system.
 */
public final class Bank {
    private final String bankId;
    private final String name;
    private final String routingNumber;
    private final String status;

    public Bank(String bankId, String name) {
        this(bankId, name, null, "active");
    }

    public Bank(String bankId, String name, String routingNumber, String status) {
        this.bankId = Objects.requireNonNull(bankId, "bankId cannot be null");
        this.name = Objects.requireNonNull(name, "name cannot be null");
        this.routingNumber = routingNumber;
        this.status = Objects.requireNonNull(status, "status cannot be null");
    }

    public String getBankId() {
        return bankId;
    }

    public String getName() {
        return name;
    }

    public String getRoutingNumber() {
        return routingNumber;
    }

    public String getStatus() {
        return status;
    }

    public boolean isActive() {
        return "active".equals(status);
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;
        Bank bank = (Bank) o;
        return Objects.equals(bankId, bank.bankId);
    }

    @Override
    public int hashCode() {
        return Objects.hash(bankId);
    }

    @Override
    public String toString() {
        return name;
    }
}

