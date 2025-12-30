package com.clearinghouse.service;

import com.clearinghouse.model.SettlementInstruction;
import com.clearinghouse.model.Transaction;

import java.math.BigDecimal;
import java.util.*;

/**
 * Multilateral netting engine that minimizes settlement transfers.
 *
 * Algorithm:
 * 1. Calculate net position per bank (sum of all inflows - outflows)
 * 2. Partition banks into creditors (net > 0) and debtors (net < 0)
 * 3. Greedily match largest creditor with largest debtor
 * 4. Generate settlement instruction for the matched amount
 * 5. Update positions and repeat until all positions are zero
 *
 * This achieves the minimum number of transfers (N-1 for N non-zero banks)
 * when there are no transfer fees to optimize for.
 */
public class NettingEngine {

    /**
     * Result of the netting process.
     */
    public static class NettingResult {
        private final Map<String, BigDecimal> netPositions;
        private final List<SettlementInstruction> instructions;
        private final BigDecimal grossVolume;
        private final BigDecimal netVolume;

        public NettingResult(Map<String, BigDecimal> netPositions,
                            List<SettlementInstruction> instructions,
                            BigDecimal grossVolume) {
            this.netPositions = netPositions;
            this.instructions = instructions;
            this.grossVolume = grossVolume;
            this.netVolume = instructions.stream()
                    .map(SettlementInstruction::getAmount)
                    .reduce(BigDecimal.ZERO, BigDecimal::add);
        }

        public Map<String, BigDecimal> getNetPositions() {
            return netPositions;
        }

        public List<SettlementInstruction> getInstructions() {
            return instructions;
        }

        public BigDecimal getGrossVolume() {
            return grossVolume;
        }

        public BigDecimal getNetVolume() {
            return netVolume;
        }

        public double getNettingEfficiency() {
            if (grossVolume.compareTo(BigDecimal.ZERO) == 0) {
                return 100.0;
            }
            return (1.0 - netVolume.doubleValue() / grossVolume.doubleValue()) * 100.0;
        }
    }

    /**
     * Calculate the net position for each bank.
     *
     * @param transactions List of transactions to process
     * @return Map from bank ID to net position (positive = receive, negative = pay)
     */
    public Map<String, BigDecimal> calculateNetPositions(List<Transaction> transactions) {
        Map<String, BigDecimal> positions = new HashMap<>();

        for (Transaction txn : transactions) {
            // Payer loses money
            positions.merge(txn.getPayer(), txn.getAmount().negate(), BigDecimal::add);
            // Payee gains money
            positions.merge(txn.getPayee(), txn.getAmount(), BigDecimal::add);
        }

        return positions;
    }

    /**
     * Validate that all positions sum to zero (system is balanced).
     *
     * @param positions Net positions per bank
     * @throws IllegalStateException if the system is unbalanced
     */
    public void validatePositions(Map<String, BigDecimal> positions) {
        BigDecimal total = positions.values().stream()
                .reduce(BigDecimal.ZERO, BigDecimal::add);

        if (total.compareTo(BigDecimal.ZERO) != 0) {
            throw new IllegalStateException(
                    "System unbalanced! Positions sum to " + total + ", expected 0. " +
                    "This indicates lost or created money.");
        }
    }

    /**
     * Generate minimal settlement instructions using greedy matching.
     *
     * Uses a heap-based approach to always match the largest creditor
     * with the largest debtor for optimal efficiency.
     *
     * @param positions Net position per bank
     * @return List of SettlementInstruction objects (minimal set)
     */
    public List<SettlementInstruction> generateSettlements(Map<String, BigDecimal> positions) {
        validatePositions(positions);

        // Max-heap for creditors (positive positions)
        // Comparator: larger amount first
        PriorityQueue<Map.Entry<String, BigDecimal>> creditors = new PriorityQueue<>(
                (a, b) -> b.getValue().compareTo(a.getValue())
        );

        // Max-heap for debtors (negative positions, compare absolute values)
        // Comparator: larger debt (more negative) first
        PriorityQueue<Map.Entry<String, BigDecimal>> debtors = new PriorityQueue<>(
                (a, b) -> a.getValue().compareTo(b.getValue())
        );

        for (Map.Entry<String, BigDecimal> entry : positions.entrySet()) {
            if (entry.getValue().compareTo(BigDecimal.ZERO) > 0) {
                creditors.add(new AbstractMap.SimpleEntry<>(entry.getKey(), entry.getValue()));
            } else if (entry.getValue().compareTo(BigDecimal.ZERO) < 0) {
                debtors.add(new AbstractMap.SimpleEntry<>(entry.getKey(), entry.getValue()));
            }
        }

        List<SettlementInstruction> instructions = new ArrayList<>();

        while (!creditors.isEmpty() && !debtors.isEmpty()) {
            Map.Entry<String, BigDecimal> creditor = creditors.poll();
            Map.Entry<String, BigDecimal> debtor = debtors.poll();

            BigDecimal creditAmount = creditor.getValue();
            BigDecimal debtAmount = debtor.getValue().abs();

            // Settlement amount is the minimum of the two
            BigDecimal settlementAmount = creditAmount.min(debtAmount);

            // Generate settlement instruction
            SettlementInstruction instruction = new SettlementInstruction(
                    debtor.getKey(),   // payer (debtor)
                    creditor.getKey(), // payee (creditor)
                    settlementAmount
            );
            instructions.add(instruction);

            // Update remaining positions
            BigDecimal remainingCredit = creditAmount.subtract(settlementAmount);
            BigDecimal remainingDebt = debtAmount.subtract(settlementAmount);

            if (remainingCredit.compareTo(BigDecimal.ZERO) > 0) {
                creditors.add(new AbstractMap.SimpleEntry<>(creditor.getKey(), remainingCredit));
            }
            if (remainingDebt.compareTo(BigDecimal.ZERO) > 0) {
                debtors.add(new AbstractMap.SimpleEntry<>(debtor.getKey(), remainingDebt.negate()));
            }
        }

        return instructions;
    }

    /**
     * Run the full settlement process for a list of transactions.
     *
     * @param transactions List of transactions to settle
     * @return NettingResult containing positions and instructions
     */
    public NettingResult runSettlement(List<Transaction> transactions) {
        // Calculate gross volume
        BigDecimal grossVolume = transactions.stream()
                .map(Transaction::getAmount)
                .reduce(BigDecimal.ZERO, BigDecimal::add);

        // Calculate net positions
        Map<String, BigDecimal> positions = calculateNetPositions(transactions);

        // Generate minimal settlement instructions
        List<SettlementInstruction> instructions = generateSettlements(positions);

        return new NettingResult(positions, instructions, grossVolume);
    }

    /**
     * Print the netting result to stdout.
     */
    public void printResult(NettingResult result, int originalTxnCount) {
        System.out.println("\nNet Positions:");
        System.out.println("-".repeat(40));

        List<String> sortedBanks = new ArrayList<>(result.getNetPositions().keySet());
        Collections.sort(sortedBanks);

        for (String bank : sortedBanks) {
            BigDecimal position = result.getNetPositions().get(bank);
            String status = position.compareTo(BigDecimal.ZERO) > 0 ? "receives" :
                           position.compareTo(BigDecimal.ZERO) < 0 ? "pays" : "flat";
            System.out.println("  " + bank + ": " + position + " (" + status + ")");
        }

        System.out.println("\nSettlement Instructions (" + result.getInstructions().size() + " transfers):");
        System.out.println("-".repeat(40));
        int i = 1;
        for (SettlementInstruction instr : result.getInstructions()) {
            System.out.println("  " + i++ + ". " + instr);
        }

        System.out.println("\nStatistics:");
        System.out.println("-".repeat(40));
        System.out.println("  Original transactions: " + originalTxnCount);
        System.out.println("  Gross volume: $" + result.getGrossVolume());
        System.out.println("  Net volume: $" + result.getNetVolume());
        System.out.printf("  Netting efficiency: %.1f%%\n", result.getNettingEfficiency());
    }
}

