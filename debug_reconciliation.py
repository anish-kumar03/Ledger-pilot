from engine.reconciler import ReconciliationEngine


def main():
    engine = ReconciliationEngine()

    output = engine.reconcile(
        "data/payments.csv",
        "data/settlements.csv",
        "data/bank_transactions.csv",
    )

    print("\n" + "=" * 80)
    print("LEDGERPILOT DEBUG REPORT")
    print("=" * 80)

    all_results = (
        output.matches
        + output.human_review_cases
        + output.exceptions
    )

    print(f"\nTotal results: {len(all_results)}")

    for index, result in enumerate(all_results[:10], start=1):
        print("\n" + "-" * 80)
        print(f"RECORD #{index}")
        print("-" * 80)

        print("Payment ID :", result.get("payment_id"))
        print("Decision   :", result.get("decision"))
        print("Reasons    :", result.get("policy_reasons"))
        print("Blocked    :", result.get("blocked_conditions"))
        print("Evidence   :", result.get("evidence"))

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()