"""Report records that actually reached the AI handoff."""

from __future__ import annotations

from pathlib import Path

from engine.reconciler import ReconciliationEngine


ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    """Run reconciliation and print AI-assisted records without credentials."""
    output = ReconciliationEngine().reconcile(
        ROOT / "data" / "payments.csv",
        ROOT / "data" / "settlements.csv",
        ROOT / "data" / "bank_transactions.csv",
    )
    print(f"AI-assisted records:  {len(output.ai_assisted_decisions)}")
    for record in output.ai_assisted_decisions:
        decision = record.get("ai_decision", {})
        print()
        print(record.get("payment_id"))
        print(f"  score: {record.get('overall_score', 0.0):.2f}")
        print(f"  AI: {decision.get('decision')}")
        print(f"  confidence: {decision.get('confidence', 0.0):.2f}")
        print(f"  selected: {decision.get('selected_bank_transaction_id')}")


if __name__ == "__main__":
    main()
