"""
Pairwise Balance Calculator for the Clearing House.

Calculates the net balance between each pair of banks from a list of transactions.
Uses alphabetically ordered tuples as keys to ensure consistent direction.
"""
from collections import defaultdict
from decimal import Decimal
from typing import Dict, List, Tuple

from models import Transaction, PairwiseKey


class PairwiseBalanceCalculator:
    """
    Calculates pairwise net balances between banks.

    For each pair of banks (A, B) where A < B alphabetically:
    - Positive balance means A owes B
    - Negative balance means B owes A

    Example:
        Transactions: Chase pays BoA $100, BoA pays Chase $30
        Result: {('BoA', 'Chase'): -70}  # Chase owes BoA $70
    """

    @staticmethod
    def _make_key(bank1: str, bank2: str) -> PairwiseKey:
        """
        Create a canonical key for a bank pair (alphabetically ordered).
        """
        if bank1 < bank2:
            return (bank1, bank2)
        return (bank2, bank1)

    @staticmethod
    def _get_sign(payer: str, payee: str) -> int:
        """
        Determine the sign for the balance update.

        Convention: For key (A, B) where A < B:
        - If A pays B: positive (A's debt to B increases)
        - If B pays A: negative (A's debt to B decreases / B owes A)
        """
        if payer < payee:
            # Payer comes first alphabetically, so payer owes payee -> positive
            return 1
        else:
            # Payee comes first alphabetically, so payee is "owed" -> negative
            return -1

    def calculate(self, transactions: List[Transaction]) -> Dict[PairwiseKey, Decimal]:
        """
        Calculate pairwise balances from a list of transactions.

        Args:
            transactions: List of Transaction objects

        Returns:
            Dictionary mapping (bank_a, bank_b) tuples to net balance.
            Positive means bank_a owes bank_b.
            Negative means bank_b owes bank_a.
        """
        balances: Dict[PairwiseKey, Decimal] = defaultdict(Decimal)

        for txn in transactions:
            key = self._make_key(txn.payer, txn.payee)
            sign = self._get_sign(txn.payer, txn.payee)
            balances[key] += sign * txn.amount

        # Remove zero balances
        return {k: v for k, v in balances.items() if v != 0}

    def calculate_from_dicts(
        self, transactions: List[Dict]
    ) -> Dict[PairwiseKey, Decimal]:
        """
        Calculate pairwise balances from a list of transaction dictionaries.

        Args:
            transactions: List of dicts with 'payer', 'payee', 'amount' keys

        Returns:
            Dictionary mapping (bank_a, bank_b) tuples to net balance.
        """
        txn_objects = [
            Transaction(
                payer=t["payer"],
                payee=t["payee"],
                amount=Decimal(str(t["amount"]))
            )
            for t in transactions
        ]
        return self.calculate(txn_objects)

    def format_balances(
        self, balances: Dict[PairwiseKey, Decimal]
    ) -> List[str]:
        """
        Format pairwise balances as human-readable strings.

        Args:
            balances: Pairwise balance dictionary

        Returns:
            List of formatted strings describing who owes whom
        """
        result = []
        for (bank_a, bank_b), amount in sorted(balances.items()):
            if amount > 0:
                result.append(f"{bank_a} owes {bank_b}: {amount}")
            else:
                result.append(f"{bank_b} owes {bank_a}: {abs(amount)}")
        return result


def demo():
    """Demonstrate pairwise balance calculation with sample data."""
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

    calculator = PairwiseBalanceCalculator()
    balances = calculator.calculate_from_dicts(sample_transactions)

    print("Pairwise Balances:")
    print("-" * 40)
    for key, value in sorted(balances.items()):
        print(f"  {key}: {value}")

    print("\nHuman-readable format:")
    print("-" * 40)
    for line in calculator.format_balances(balances):
        print(f"  {line}")


if __name__ == "__main__":
    demo()

