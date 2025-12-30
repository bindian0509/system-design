package com.clearinghouse.model;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.Objects;
import java.util.UUID;

/**
 * Immutable transaction record representing a payment instruction.
 *
 * A transaction flows from payer (sender) to payee (receiver).
 * Amount is always positive; direction is determined by payer/payee.
 */
public final class Transaction {
    private final String txnId;
    private final String payer;
    private final String payee;
    private final BigDecimal amount;
    private final String currency;
    private final Instant ingestTs;

    public Transaction(String payer, String payee, BigDecimal amount) {
        this(UUID.randomUUID().toString(), payer, payee, amount, "USD", Instant.now());
    }

    public Transaction(String txnId, String payer, String payee, BigDecimal amount,
                       String currency, Instant ingestTs) {
        if (amount.compareTo(BigDecimal.ZERO) <= 0) {
            throw new IllegalArgumentException("Transaction amount must be positive, got " + amount);
        }
        if (payer.equals(payee)) {
            throw new IllegalArgumentException("Payer and payee cannot be the same bank");
        }

        this.txnId = txnId;
        this.payer = Objects.requireNonNull(payer, "payer cannot be null");
        this.payee = Objects.requireNonNull(payee, "payee cannot be null");
        this.amount = Objects.requireNonNull(amount, "amount cannot be null");
        this.currency = Objects.requireNonNull(currency, "currency cannot be null");
        this.ingestTs = Objects.requireNonNull(ingestTs, "ingestTs cannot be null");
    }

    public String getTxnId() {
        return txnId;
    }

    public String getPayer() {
        return payer;
    }

    public String getPayee() {
        return payee;
    }

    public BigDecimal getAmount() {
        return amount;
    }

    public String getCurrency() {
        return currency;
    }

    public Instant getIngestTs() {
        return ingestTs;
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;
        Transaction that = (Transaction) o;
        return Objects.equals(txnId, that.txnId);
    }

    @Override
    public int hashCode() {
        return Objects.hash(txnId);
    }

    @Override
    public String toString() {
        return payer + " → " + payee + ": " + amount + " " + currency;
    }
}

