package com.clearinghouse;

import com.clearinghouse.model.PairwiseKey;
import com.clearinghouse.model.Transaction;
import com.clearinghouse.service.NettingEngine;
import com.clearinghouse.service.PairwiseBalanceCalculator;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * Settlement Application - Demo Entry Point
 *
 * Demonstrates the complete clearing house workflow:
 * 1. Transaction ingestion
 * 2. Pairwise balance calculation (Part 1)
 * 3. Multilateral netting optimization (Part 2)
 * 4. Settlement instruction generation
 */
public class SettlementApp {

    public static void main(String[] args) {
        System.out.println("=".repeat(70));
        System.out.println("FINANCIAL CLEARING HOUSE - JAVA IMPLEMENTATION");
        System.out.println("=".repeat(70));

        // Sample transactions from the problem statement
        List<Transaction> transactions = createSampleTransactions();

        System.out.println("\nInput Transactions:");
        System.out.println("-".repeat(40));
        int i = 1;
        for (Transaction txn : transactions) {
            System.out.println("  " + i++ + ". " + txn);
        }

        // =====================================================================
        // PART 1: Pairwise Balance Calculation
        // =====================================================================
        System.out.println("\n" + "=".repeat(70));
        System.out.println("PART 1: PAIRWISE BALANCE CALCULATION");
        System.out.println("=".repeat(70));
        System.out.println("""

            This calculates the net balance between each pair of banks.
            For pair (A, B) where A < B alphabetically:
              - Positive balance means A owes B
              - Negative balance means B owes A
            """);

        PairwiseBalanceCalculator pairwiseCalculator = new PairwiseBalanceCalculator();
        Map<PairwiseKey, BigDecimal> pairwiseBalances = pairwiseCalculator.calculate(transactions);

        pairwiseCalculator.printBalances(pairwiseBalances);

        System.out.println("\nInterpretation:");
        for (String line : pairwiseCalculator.formatBalances(pairwiseBalances)) {
            System.out.println("  • " + line);
        }

        // =====================================================================
        // PART 2: Transaction Optimization (Multilateral Netting)
        // =====================================================================
        System.out.println("\n" + "=".repeat(70));
        System.out.println("PART 2: TRANSACTION OPTIMIZATION (MULTILATERAL NETTING)");
        System.out.println("=".repeat(70));
        System.out.println("""

            This reduces the number of actual money movements by:
            1. Calculating each bank's net position (total in - total out)
            2. Matching creditors with debtors to generate minimal transfers
            """);

        NettingEngine nettingEngine = new NettingEngine();
        NettingEngine.NettingResult result = nettingEngine.runSettlement(transactions);

        nettingEngine.printResult(result, transactions.size());

        // =====================================================================
        // SUMMARY
        // =====================================================================
        System.out.println("\n" + "=".repeat(70));
        System.out.println("SUMMARY");
        System.out.println("=".repeat(70));
        System.out.printf("""

            Original Transactions: %d
            Gross Volume:          $%s
            Final Transfers:       %d
            Net Volume:            $%s
            Netting Efficiency:    %.1f%%

            The netting process reduced the number of interbank transfers
            from %d to %d, saving %d transfers!
            """,
                transactions.size(),
                result.getGrossVolume(),
                result.getInstructions().size(),
                result.getNetVolume(),
                result.getNettingEfficiency(),
                transactions.size(),
                result.getInstructions().size(),
                transactions.size() - result.getInstructions().size()
        );
    }

    /**
     * Create sample transactions from the problem statement.
     */
    private static List<Transaction> createSampleTransactions() {
        List<Transaction> transactions = new ArrayList<>();

        // Sample transactions: {"payee": "BoA", "amount": 132, "payer": "Chase"}, etc.
        transactions.add(new Transaction("Chase", "BoA", new BigDecimal("132")));
        transactions.add(new Transaction("Chase", "BoA", new BigDecimal("827")));
        transactions.add(new Transaction("BoA", "Wells Fargo", new BigDecimal("751")));
        transactions.add(new Transaction("Chase", "BoA", new BigDecimal("585")));
        transactions.add(new Transaction("Wells Fargo", "Chase", new BigDecimal("877")));
        transactions.add(new Transaction("Chase", "Wells Fargo", new BigDecimal("157")));
        transactions.add(new Transaction("Chase", "Wells Fargo", new BigDecimal("904")));
        transactions.add(new Transaction("Wells Fargo", "Chase", new BigDecimal("548")));
        transactions.add(new Transaction("BoA", "Chase", new BigDecimal("976")));

        return transactions;
    }
}

