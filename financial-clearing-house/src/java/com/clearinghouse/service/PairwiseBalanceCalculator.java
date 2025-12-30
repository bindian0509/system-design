package com.clearinghouse.service;

import com.clearinghouse.model.PairwiseKey;
import com.clearinghouse.model.Transaction;

import java.math.BigDecimal;
import java.util.*;

/**
 * Calculates pairwise net balances between banks.
 *
 * For each pair of banks (A, B) where A < B alphabetically:
 * - Positive balance means A owes B
 * - Negative balance means B owes A
 *
 * Example:
 *   Transactions: Chase pays BoA $100, BoA pays Chase $30
 *   Result: {(BoA, Chase): -70}  // Chase owes BoA $70
 */
public class PairwiseBalanceCalculator {

    /**
     * Calculate pairwise balances from a list of transactions.
     *
     * @param transactions List of Transaction objects
     * @return Map from PairwiseKey to net balance (positive means bankA owes bankB)
     */
    public Map<PairwiseKey, BigDecimal> calculate(List<Transaction> transactions) {
        Map<PairwiseKey, BigDecimal> balances = new HashMap<>();

        for (Transaction txn : transactions) {
            PairwiseKey key = PairwiseKey.of(txn.getPayer(), txn.getPayee());
            int sign = key.getSign(txn.getPayer());

            BigDecimal current = balances.getOrDefault(key, BigDecimal.ZERO);
            BigDecimal delta = txn.getAmount().multiply(BigDecimal.valueOf(sign));
            balances.put(key, current.add(delta));
        }

        // Remove zero balances
        balances.entrySet().removeIf(e -> e.getValue().compareTo(BigDecimal.ZERO) == 0);

        return balances;
    }

    /**
     * Format pairwise balances as human-readable strings.
     *
     * @param balances Pairwise balance map
     * @return List of formatted strings describing who owes whom
     */
    public List<String> formatBalances(Map<PairwiseKey, BigDecimal> balances) {
        List<String> result = new ArrayList<>();

        List<PairwiseKey> sortedKeys = new ArrayList<>(balances.keySet());
        Collections.sort(sortedKeys);

        for (PairwiseKey key : sortedKeys) {
            BigDecimal amount = balances.get(key);
            if (amount.compareTo(BigDecimal.ZERO) > 0) {
                result.add(key.getBankA() + " owes " + key.getBankB() + ": " + amount);
            } else {
                result.add(key.getBankB() + " owes " + key.getBankA() + ": " + amount.abs());
            }
        }

        return result;
    }

    /**
     * Print pairwise balances to stdout.
     */
    public void printBalances(Map<PairwiseKey, BigDecimal> balances) {
        System.out.println("Pairwise Balances (alphabetical; positive means first owes second):");

        List<PairwiseKey> sortedKeys = new ArrayList<>(balances.keySet());
        Collections.sort(sortedKeys);

        for (PairwiseKey key : sortedKeys) {
            System.out.println("  " + key + " : " + balances.get(key));
        }
    }
}

