"""
Netting Engine for the Clearing House.

Implements multilateral netting to minimize the number of actual money movements.
Uses a greedy creditor-debtor matching algorithm that achieves O(N-1) transfers
for N banks with non-zero positions.
"""
from collections import defaultdict
from decimal import Decimal
from typing import Dict, List, Tuple
from dataclasses import dataclass
import heapq

from models import Transaction, SettlementInstruction, SettlementBatch


@dataclass
class NetPosition:
    """
    Net position of a bank after processing all transactions.

    Positive = bank is a creditor (will receive money)
    Negative = bank is a debtor (must pay money)
    """
    bank: str
    amount: Decimal

    def is_creditor(self) -> bool:
        return self.amount > 0

    def is_debtor(self) -> bool:
        return self.amount < 0

    def is_flat(self) -> bool:
        return self.amount == 0


class NettingEngine:
    """
    Multilateral netting engine that minimizes settlement transfers.

    Algorithm:
    1. Calculate net position per bank (sum of all inflows - outflows)
    2. Partition banks into creditors (net > 0) and debtors (net < 0)
    3. Greedily match largest creditor with largest debtor
    4. Generate settlement instruction for the matched amount
    5. Update positions and repeat until all positions are zero

    This achieves the minimum number of transfers (N-1 for N non-zero banks)
    when there are no transfer fees to optimize for.
    """

    def calculate_net_positions(
        self, transactions: List[Transaction]
    ) -> Dict[str, Decimal]:
        """
        Calculate the net position for each bank.

        Args:
            transactions: List of transactions to process

        Returns:
            Dictionary mapping bank_id to net position
            (positive = receive, negative = pay)
        """
        positions: Dict[str, Decimal] = defaultdict(Decimal)

        for txn in transactions:
            # Payer loses money
            positions[txn.payer] -= txn.amount
            # Payee gains money
            positions[txn.payee] += txn.amount

        return dict(positions)

    def validate_positions(self, positions: Dict[str, Decimal]) -> bool:
        """
        Validate that all positions sum to zero (system is balanced).

        Raises:
            ValueError: If the system is unbalanced
        """
        total = sum(positions.values())
        if total != 0:
            raise ValueError(
                f"System unbalanced! Positions sum to {total}, expected 0. "
                "This indicates lost or created money."
            )
        return True

    def generate_settlements(
        self, positions: Dict[str, Decimal]
    ) -> List[SettlementInstruction]:
        """
        Generate minimal settlement instructions using greedy matching.

        Uses a heap-based approach to always match the largest creditor
        with the largest debtor for optimal efficiency.

        Args:
            positions: Net position per bank

        Returns:
            List of SettlementInstruction objects (minimal set)
        """
        self.validate_positions(positions)

        # Separate into creditors and debtors using max-heaps
        # Python heapq is min-heap, so negate values for max-heap behavior
        creditors: List[Tuple[Decimal, str]] = []
        debtors: List[Tuple[Decimal, str]] = []

        for bank, amount in positions.items():
            if amount > 0:
                # Negate for max-heap (largest creditor first)
                heapq.heappush(creditors, (-amount, bank))
            elif amount < 0:
                # Already negative, push as-is for max-heap (largest debtor first)
                heapq.heappush(debtors, (amount, bank))

        instructions: List[SettlementInstruction] = []

        while creditors and debtors:
            # Get largest creditor and debtor
            neg_credit, creditor = heapq.heappop(creditors)
            debt, debtor = heapq.heappop(debtors)

            credit_amount = -neg_credit  # Restore positive value
            debt_amount = -debt  # Convert to positive for comparison

            # Settlement amount is the minimum of the two
            settlement_amount = min(credit_amount, debt_amount)

            # Generate settlement instruction
            instruction = SettlementInstruction(
                payer=debtor,
                payee=creditor,
                amount=settlement_amount
            )
            instructions.append(instruction)

            # Update remaining positions
            remaining_credit = credit_amount - settlement_amount
            remaining_debt = debt_amount - settlement_amount

            if remaining_credit > 0:
                heapq.heappush(creditors, (-remaining_credit, creditor))
            if remaining_debt > 0:
                heapq.heappush(debtors, (-remaining_debt, debtor))

        return instructions

    def run_settlement(
        self, transactions: List[Transaction], batch_id: str = None
    ) -> SettlementBatch:
        """
        Run the full settlement process for a list of transactions.

        Args:
            transactions: List of transactions to settle
            batch_id: Optional batch identifier

        Returns:
            SettlementBatch containing positions and instructions
        """
        batch = SettlementBatch(batch_id=batch_id) if batch_id else SettlementBatch()

        # Store source transactions
        for txn in transactions:
            batch.add_transaction(txn)

        # Calculate net positions
        positions = self.calculate_net_positions(transactions)
        batch.net_positions = positions

        # Generate minimal settlement instructions
        instructions = self.generate_settlements(positions)
        for instr in instructions:
            batch.add_instruction(instr)

        return batch

    def run_settlement_from_dicts(
        self, transactions: List[Dict], batch_id: str = None
    ) -> SettlementBatch:
        """
        Run settlement from transaction dictionaries.

        Args:
            transactions: List of dicts with 'payer', 'payee', 'amount' keys
            batch_id: Optional batch identifier

        Returns:
            SettlementBatch containing positions and instructions
        """
        txn_objects = [
            Transaction(
                payer=t["payer"],
                payee=t["payee"],
                amount=Decimal(str(t["amount"]))
            )
            for t in transactions
        ]
        return self.run_settlement(txn_objects, batch_id)


def demo():
    """Demonstrate the netting engine with sample data."""
    # Sample transactions from the problem statement
    sample_transactions = [
        {"payee": "BoA", "amount": 132, "payer": "Chase"},
        {"payee": "BoA", "amount": 827, "payer": "Chase"},
        {"payee": "Wells Fargo", "amount": 751, "payer": "BoA"},
        {"payee": "BoA", "amount": 585, "payer": "Chase"},
        {"payee": "Chase", "amount": 877, "payer": "Wells Fargo"},
        {"payee": "Wells Fargo", "amount": 157, "payer": "Chase"},
        {"payee": "Wells Fargo", "amount": 904, "payer": "Chase"},
        {"payee": "Chase", "amount": 548, "payer": "Wells Fargo"},
        {"payee": "Chase", "amount": 976, "payer": "BoA"},
    ]

    engine = NettingEngine()
    batch = engine.run_settlement_from_dicts(sample_transactions)

    print("Net Positions:")
    print("-" * 40)
    for bank, position in sorted(batch.net_positions.items()):
        if position > 0:
            print(f"  {bank}: +{position} (receives)")
        elif position < 0:
            print(f"  {bank}: {position} (pays)")
        else:
            print(f"  {bank}: 0 (flat)")

    print(f"\nSettlement Instructions ({len(batch.instructions)} transfers):")
    print("-" * 40)
    for instr in batch.instructions:
        print(f"  {instr}")

    print(f"\nNetting Statistics:")
    print("-" * 40)
    print(f"  Original transactions: {len(batch.source_transactions)}")
    print(f"  Gross volume: ${batch.total_gross_volume()}")
    print(f"  Net volume: ${batch.total_net_volume()}")
    print(f"  Netting efficiency: {batch.netting_efficiency():.1f}%")


if __name__ == "__main__":
    demo()

