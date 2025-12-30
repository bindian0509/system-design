package com.clearinghouse.service;

import com.clearinghouse.model.Transaction;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/**
 * Validates transactions before processing.
 *
 * In production, this would include:
 * - AML/KYC checks
 * - Sanctions screening
 * - Credit limit validation
 * - Signature verification
 */
public class TransactionValidator {

    private final Set<String> processedTxnIds = new HashSet<>();

    /**
     * Validation result containing valid transactions and any rejected ones.
     */
    public static class ValidationResult {
        private final List<Transaction> valid;
        private final List<String> rejectionReasons;

        public ValidationResult(List<Transaction> valid, List<String> rejectionReasons) {
            this.valid = valid;
            this.rejectionReasons = rejectionReasons;
        }

        public List<Transaction> getValid() {
            return valid;
        }

        public List<String> getRejectionReasons() {
            return rejectionReasons;
        }

        public boolean hasRejections() {
            return !rejectionReasons.isEmpty();
        }
    }

    /**
     * Validate a batch of transactions.
     *
     * @param transactions Transactions to validate
     * @return ValidationResult with valid transactions and rejection reasons
     */
    public ValidationResult validate(List<Transaction> transactions) {
        List<Transaction> valid = new ArrayList<>();
        List<String> rejections = new ArrayList<>();

        for (Transaction txn : transactions) {
            List<String> errors = validateSingle(txn);
            if (errors.isEmpty()) {
                valid.add(txn);
                processedTxnIds.add(txn.getTxnId());
            } else {
                rejections.addAll(errors);
            }
        }

        return new ValidationResult(valid, rejections);
    }

    /**
     * Validate a single transaction.
     *
     * @param txn Transaction to validate
     * @return List of validation errors (empty if valid)
     */
    public List<String> validateSingle(Transaction txn) {
        List<String> errors = new ArrayList<>();

        // Check for duplicate transaction ID (idempotency)
        if (processedTxnIds.contains(txn.getTxnId())) {
            errors.add("Duplicate transaction ID: " + txn.getTxnId());
        }

        // Amount must be positive
        if (txn.getAmount().compareTo(BigDecimal.ZERO) <= 0) {
            errors.add("Invalid amount for txn " + txn.getTxnId() + ": " + txn.getAmount());
        }

        // Self-payment not allowed
        if (txn.getPayer().equals(txn.getPayee())) {
            errors.add("Self-payment not allowed for txn " + txn.getTxnId());
        }

        // Payer and payee cannot be null/empty (already checked in constructor, but defensive)
        if (txn.getPayer() == null || txn.getPayer().isEmpty()) {
            errors.add("Missing payer for txn " + txn.getTxnId());
        }
        if (txn.getPayee() == null || txn.getPayee().isEmpty()) {
            errors.add("Missing payee for txn " + txn.getTxnId());
        }

        return errors;
    }

    /**
     * Clear the processed transaction ID cache.
     * Used for testing or batch resets.
     */
    public void reset() {
        processedTxnIds.clear();
    }
}

