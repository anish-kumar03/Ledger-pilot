from engine.reconciler import ReconciliationEngine


def main():
    print("=" * 60)
    print("LEDGERPILOT - RECONCILIATION RUN")
    print("=" * 60)

    engine = ReconciliationEngine()

    output = engine.reconcile(
        "data/payments.csv",
        "data/settlements.csv",
        "data/bank_transactions.csv",
    )

    total = (
        len(output.matches)
        + len(output.human_review_cases)
        + len(output.exceptions)
    )

    print(f"Total processed : {total}")
    print(f"Matches         : {len(output.matches)}")
    print(f"AI assisted     : {len(output.ai_assisted_decisions)}")
    print(f"Human review    : {len(output.human_review_cases)}")
    print(f"Exceptions      : {len(output.exceptions)}")
    print(f"Audit events    : {len(output.audit_events)}")

    print("=" * 60)


if __name__ == "__main__":
    main()