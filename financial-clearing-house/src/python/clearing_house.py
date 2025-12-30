"""
Clearing House - Main Orchestrator

Coordinates the end-of-day settlement process:
1. Ingest transactions throughout the day
2. Calculate pairwise balances between banks
3. Run multilateral netting to minimize transfers
4. Generate settlement instructions
"""
from decimal import Decimal
from typing import Dict, List, Optional
from datetime import datetime
import uuid

from models import (
    Transaction,
    SettlementInstruction,
    SettlementBatch,
    TransactionStatus,
    PairwiseKey,
)
from pairwise_calculator import PairwiseBalanceCalculator
from netting_engine import NettingEngine


class ClearingHouse:
    """
    Main clearing house orchestrator.

    Manages the full lifecycle of transaction processing:
    - Transaction ingestion and validation
    - Pairwise balance calculation (Part 1)
    - Multilateral netting and optimization (Part 2)
    - Settlement instruction generation
    """

    def __init__(self, name: str = "ClearingHouse"):
        self.name = name
        self.transactions: List[Transaction] = []
        self.pairwise_calculator = PairwiseBalanceCalculator()
        self.netting_engine = NettingEngine()
        self.settlement_batches: List[SettlementBatch] = []

    def submit_transaction(self, txn: Transaction) -> bool:
        """
        Submit a transaction for processing.

        Args:
            txn: Transaction to process

        Returns:
            True if accepted, False if rejected
        """
        # Basic validation (in production, would include AML/KYC, limits, etc.)
        if txn.amount <= 0:
            print(f"REJECTED: Invalid amount {txn.amount}")
            return False
        if txn.payer == txn.payee:
            print(f"REJECTED: Self-payment not allowed")
            return False

        self.transactions.append(txn)
        print(f"INGESTED: {txn}")
        return True

    def submit_from_dict(self, data: Dict) -> bool:
        """
        Submit a transaction from a dictionary.

        Args:
            data: Dict with 'payer', 'payee', 'amount' keys

        Returns:
            True if accepted, False if rejected
        """
        try:
            txn = Transaction(
                payer=data["payer"],
                payee=data["payee"],
                amount=Decimal(str(data["amount"]))
            )
            return self.submit_transaction(txn)
        except (KeyError, ValueError) as e:
            print(f"REJECTED: Invalid transaction data - {e}")
            return False

    def get_pairwise_balances(self) -> Dict[PairwiseKey, Decimal]:
        """
        Calculate pairwise balances for all ingested transactions.

        Returns:
            Dictionary mapping (bank_a, bank_b) tuples to net balance.
            Positive means bank_a owes bank_b.
        """
        return self.pairwise_calculator.calculate(self.transactions)

    def run_eod_settlement(self, batch_id: str = None) -> SettlementBatch:
        """
        Run end-of-day settlement process.

        This calculates net positions and generates minimal settlement
        instructions using multilateral netting.

        Args:
            batch_id: Optional batch identifier

        Returns:
            SettlementBatch with all settlement details
        """
        if not self.transactions:
            print("No transactions to settle")
            return SettlementBatch()

        print(f"\n{'='*60}")
        print(f"STARTING END-OF-DAY SETTLEMENT")
        print(f"{'='*60}")
        print(f"Processing {len(self.transactions)} transactions...")

        # Run netting
        batch = self.netting_engine.run_settlement(
            self.transactions,
            batch_id=batch_id or str(uuid.uuid4())
        )

        # Store batch for historical reference
        self.settlement_batches.append(batch)

        # Generate report
        self._print_settlement_report(batch)

        # Clear processed transactions
        self.transactions = []

        return batch

    def _print_settlement_report(self, batch: SettlementBatch):
        """Print a detailed settlement report."""
        print(f"\n--- NET POSITIONS ---")
        for bank, position in sorted(batch.net_positions.items()):
            if position > 0:
                print(f"  {bank}: RECEIVES ${position}")
            elif position < 0:
                print(f"  {bank}: PAYS ${abs(position)}")
            else:
                print(f"  {bank}: FLAT (no transfer needed)")

        print(f"\n--- SETTLEMENT INSTRUCTIONS ---")
        print(f"(Optimized from {len(batch.source_transactions)} to "
              f"{len(batch.instructions)} transfers)")
        for i, instr in enumerate(batch.instructions, 1):
            print(f"  {i}. {instr}")

        print(f"\n--- STATISTICS ---")
        print(f"  Gross Volume: ${batch.total_gross_volume()}")
        print(f"  Net Volume:   ${batch.total_net_volume()}")
        print(f"  Reduction:    {batch.netting_efficiency():.1f}%")
        print(f"{'='*60}\n")

    def get_historical_batch(self, batch_id: str) -> Optional[SettlementBatch]:
        """Retrieve a historical settlement batch by ID."""
        for batch in self.settlement_batches:
            if batch.batch_id == batch_id:
                return batch
        return None


def run_demo():
    """
    Demonstrate the full clearing house workflow with sample data.
    """
    print("\n" + "="*60)
    print("CLEARING HOUSE DEMONSTRATION")
    print("="*60 + "\n")

    # Initialize clearing house
    ch = ClearingHouse(name="Demo Clearing House")

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

    print("--- INGESTING TRANSACTIONS ---")
    for txn_data in sample_transactions:
        ch.submit_from_dict(txn_data)

    # Part 1: Show pairwise balances
    print("\n--- PAIRWISE BALANCES (Part 1) ---")
    pairwise = ch.get_pairwise_balances()
    for (bank_a, bank_b), amount in sorted(pairwise.items()):
        if amount > 0:
            print(f"  {bank_a} owes {bank_b}: ${amount}")
        else:
            print(f"  {bank_b} owes {bank_a}: ${abs(amount)}")
    print(f"\nRaw format: {dict(pairwise)}")

    # Part 2: Run settlement with optimization
    batch = ch.run_eod_settlement()

    print("Settlement complete!")
    print(f"Batch ID: {batch.batch_id}")


if __name__ == "__main__":
    run_demo()

