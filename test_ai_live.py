"""Local live Groq smoke test using one synthetic ambiguous case."""

from ai.agent import ReconciliationAgent


def main() -> None:
    """Call Groq and print only the structured reconciliation decision."""
    decision = ReconciliationAgent().reason(
        payment={
            "payment_id": "PAY-LIVE-001",
            "transaction_reference": "ORD-2026-AMB-001",
            "merchant_name": "Northstar Books",
            "invoice_id": "INV-LIVE-001",
            "payment_date": "2026-09-04",
        },
        settlement={
            "settlement_id": "SET-LIVE-001",
            "net_amount": "604.27",
            "settlement_date": "2026-09-06",
        },
        bank_candidates=[
            {
                "bank_transaction_id": "BANK-LIVE-001",
                "transaction_reference": "ORD-2026-AMB-001",
                "merchant_name": "Northstar Bookstore",
                "amount": "604.27",
                "transaction_date": "2026-09-07",
            },
            {
                "bank_transaction_id": "BANK-LIVE-002",
                "transaction_reference": "ORD-2026-AMB-001",
                "merchant_name": "North Star Books",
                "amount": "604.25",
                "transaction_date": "2026-09-06",
            },
        ],
        deterministic_evidence={
            "reason": "Two plausible synthetic bank candidates require review"
        },
    )
    print(f"AI decision: {decision.decision}")
    print(f"Confidence: {decision.confidence:.2f}")
    print(f"Selected candidate: {decision.selected_bank_transaction_id}")
    print(f"Reason codes: {decision.reason_codes}")
    print(f"Explanation: {decision.explanation}")


if __name__ == "__main__":
    main()
