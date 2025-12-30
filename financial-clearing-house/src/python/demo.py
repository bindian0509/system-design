#!/usr/bin/env python3
"""
Clearing House Demo Script

Runs a complete demonstration of the clearing house system including:
- Transaction ingestion
- Pairwise balance calculation
- Multilateral netting optimization
- Settlement instruction generation

Usage:
    python demo.py
"""
from decimal import Decimal
from clearing_house import ClearingHouse
from pairwise_calculator import PairwiseBalanceCalculator
from netting_engine import NettingEngine


def main():
    """Run the complete clearing house demonstration."""

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

    print("=" * 70)
    print("FINANCIAL CLEARING HOUSE - COMPLETE DEMONSTRATION")
    print("=" * 70)

    # =========================================================================
    # PART 1: Pairwise Balance Calculation
    # =========================================================================
    print("\n" + "=" * 70)
    print("PART 1: PAIRWISE BALANCE CALCULATION")
    print("=" * 70)
    print("""
This calculates the net balance between each pair of banks.
For pair (A, B) where A < B alphabetically:
  - Positive balance means A owes B
  - Negative balance means B owes A
""")

    calculator = PairwiseBalanceCalculator()
    pairwise = calculator.calculate_from_dicts(sample_transactions)

    print("Input Transactions:")
    for i, txn in enumerate(sample_transactions, 1):
        print(f"  {i}. {txn['payer']} → {txn['payee']}: ${txn['amount']}")

    print("\nPairwise Balances:")
    for (bank_a, bank_b), amount in sorted(pairwise.items()):
        print(f"  ({bank_a}, {bank_b}): {amount}")

    print("\nInterpretation:")
    for line in calculator.format_balances(pairwise):
        print(f"  • {line}")

    # =========================================================================
    # PART 2: Transaction Optimization (Multilateral Netting)
    # =========================================================================
    print("\n" + "=" * 70)
    print("PART 2: TRANSACTION OPTIMIZATION (MULTILATERAL NETTING)")
    print("=" * 70)
    print("""
This reduces the number of actual money movements by:
1. Calculating each bank's net position (total in - total out)
2. Matching creditors with debtors to generate minimal transfers
""")

    engine = NettingEngine()
    batch = engine.run_settlement_from_dicts(sample_transactions)

    print("Net Positions:")
    for bank, position in sorted(batch.net_positions.items()):
        status = "receives" if position > 0 else "pays" if position < 0 else "flat"
        print(f"  {bank}: {position:+} ({status})")

    print(f"\nOptimized Settlement Instructions:")
    print(f"(Reduced from {len(sample_transactions)} original transactions "
          f"to {len(batch.instructions)} transfers)")
    for i, instr in enumerate(batch.instructions, 1):
        print(f"  {i}. {instr.payer} pays {instr.payee}: ${instr.amount}")

    # =========================================================================
    # FULL WORKFLOW: Using the ClearingHouse Orchestrator
    # =========================================================================
    print("\n" + "=" * 70)
    print("FULL WORKFLOW: CLEARING HOUSE ORCHESTRATION")
    print("=" * 70)
    print("""
The ClearingHouse class orchestrates the complete settlement process,
simulating a real end-of-day batch settlement.
""")

    ch = ClearingHouse(name="Demo Clearing House")

    print("Ingesting transactions...")
    for txn_data in sample_transactions:
        ch.submit_from_dict(txn_data)

    # Run EOD settlement
    batch = ch.run_eod_settlement()

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"""
Original Transactions: {len(sample_transactions)}
Gross Volume:          ${batch.total_gross_volume()}
Final Transfers:       {len(batch.instructions)}
Net Volume:            ${batch.total_net_volume()}
Netting Efficiency:    {batch.netting_efficiency():.1f}%

The netting process reduced the number of interbank transfers
from {len(sample_transactions)} to {len(batch.instructions)},
saving {len(sample_transactions) - len(batch.instructions)} transfers!
""")


if __name__ == "__main__":
    main()

