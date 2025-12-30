package com.clearinghouse.model;

import java.util.Objects;

/**
 * Canonical key for a bank pair (alphabetically ordered).
 *
 * Used to ensure consistent direction when calculating pairwise balances.
 * The first bank is always alphabetically smaller than the second.
 */
public final class PairwiseKey implements Comparable<PairwiseKey> {
    private final String bankA;
    private final String bankB;

    /**
     * Create a pairwise key from two banks, ordering them alphabetically.
     */
    public static PairwiseKey of(String bank1, String bank2) {
        if (bank1.compareTo(bank2) < 0) {
            return new PairwiseKey(bank1, bank2);
        } else {
            return new PairwiseKey(bank2, bank1);
        }
    }

    private PairwiseKey(String bankA, String bankB) {
        this.bankA = Objects.requireNonNull(bankA);
        this.bankB = Objects.requireNonNull(bankB);
    }

    public String getBankA() {
        return bankA;
    }

    public String getBankB() {
        return bankB;
    }

    /**
     * Get the sign for a balance update based on payer direction.
     *
     * Convention:
     * - If payer == bankA (first alphabetically): positive (A owes B)
     * - If payer == bankB: negative (B owes A)
     */
    public int getSign(String payer) {
        if (payer.equals(bankA)) {
            return 1;  // A pays B -> A owes B -> positive
        } else {
            return -1; // B pays A -> B owes A -> negative
        }
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;
        PairwiseKey that = (PairwiseKey) o;
        return Objects.equals(bankA, that.bankA) && Objects.equals(bankB, that.bankB);
    }

    @Override
    public int hashCode() {
        return Objects.hash(bankA, bankB);
    }

    @Override
    public int compareTo(PairwiseKey other) {
        int cmp = this.bankA.compareTo(other.bankA);
        if (cmp != 0) return cmp;
        return this.bankB.compareTo(other.bankB);
    }

    @Override
    public String toString() {
        return "(" + bankA + ", " + bankB + ")";
    }
}

