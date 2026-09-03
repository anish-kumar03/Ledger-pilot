"""Evaluate the real LedgerPilot reconciliation engine against ground truth."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from engine.reconciler import ReconciliationEngine, ReconciliationOutput
from evaluation.metrics import calculate_all_metrics


ROOT = Path(__file__).resolve().parent.parent
PAYMENTS_PATH = ROOT / "data" / "payments.csv"
SETTLEMENTS_PATH = ROOT / "data" / "settlements.csv"
BANK_TRANSACTIONS_PATH = ROOT / "data" / "bank_transactions.csv"
GROUND_TRUTH_PATH = ROOT / "data" / "ground_truth.csv"


def load_ground_truth(path: str | Path) -> pd.DataFrame:
    """Load ground-truth reconciliation relationships from CSV."""
    return pd.read_csv(path)


def _candidate_fields(entry: dict[str, Any]) -> dict[str, Any]:
    """Extract candidate identity from an engine output entry."""
    evidence = entry.get("evidence") or []
    candidate = evidence[0] if evidence and isinstance(evidence[0], dict) else {}
    return {
        "settlement_id": entry.get("settlement_id") or candidate.get("settlement_id"),
        "bank_transaction_id": entry.get("bank_transaction_id")
        or candidate.get("bank_transaction_id"),
    }


def normalize_reconciliation_output(output: ReconciliationOutput) -> list[dict[str, Any]]:
    """Flatten engine result buckets into one evaluation record per payment."""
    ai_payment_ids = {
        str(entry["payment_id"])
        for entry in output.ai_assisted_decisions
        if entry.get("payment_id") is not None
    }
    normalized: list[dict[str, Any]] = []
    for bucket_name, entries in (
        ("matches", output.matches),
        ("human_review_cases", output.human_review_cases),
        ("exceptions", output.exceptions),
    ):
        for entry in entries:
            payment_id = entry.get("payment_id")
            fields = _candidate_fields(entry)
            normalized.append(
                {
                    "payment_id": str(payment_id) if payment_id is not None else None,
                    "settlement_id": fields["settlement_id"],
                    "bank_transaction_id": fields["bank_transaction_id"],
                    "decision": entry.get("decision"),
                    "auto_matched": entry.get("decision") == "AUTO_MATCH",
                    "ai_assisted": payment_id is not None and str(payment_id) in ai_payment_ids,
                    "reason_codes": entry.get("policy_reasons", [])
                    + entry.get("blocked_conditions", []),
                    "evidence": entry.get("evidence", []),
                    "_source_bucket": bucket_name,
                }
            )
    _validate_unique_ids(normalized, "Reconciliation output")
    return normalized


def _validate_unique_ids(records: list[dict[str, Any]], label: str) -> set[str]:
    """Require non-empty and unique payment IDs."""
    if any(not record.get("payment_id") for record in records):
        raise ValueError(f"{label} contains a record with a missing payment_id")
    ids = [str(record["payment_id"]) for record in records]
    duplicates = sorted({payment_id for payment_id in ids if ids.count(payment_id) > 1})
    if duplicates:
        raise ValueError(f"{label} contains duplicate payment IDs: {', '.join(duplicates)}")
    return set(ids)


def compare_with_ground_truth(
    results: list[dict[str, Any]],
    ground_truth: pd.DataFrame,
) -> list[dict[str, Any]]:
    """Annotate every result and reject missing, unexpected, or duplicate IDs."""
    result_ids = _validate_unique_ids(results, "Reconciliation output")
    truth_records = ground_truth.to_dict(orient="records")
    truth_ids = _validate_unique_ids(truth_records, "Ground truth")
    missing_truth = sorted(result_ids - truth_ids)
    unexpected_truth = sorted(truth_ids - result_ids)
    if missing_truth:
        raise ValueError("Missing ground truth for payment IDs: " + ", ".join(missing_truth))
    if unexpected_truth:
        raise ValueError(
            "Ground truth contains unexpected payment IDs: " + ", ".join(unexpected_truth)
        )

    truth_by_payment = {str(row["payment_id"]): row for row in truth_records}
    evaluated: list[dict[str, Any]] = []
    for result in results:
        row = dict(result)
        truth = truth_by_payment[str(row["payment_id"])]
        expected_status = str(truth["expected_status"])
        expected_bank_ids = {
            bank_id
            for bank_id in str(truth.get("bank_transaction_ids", "")).split(";")
            if bank_id
        }
        expected_match = expected_status.startswith("matched")
        actual_match = row.get("auto_matched") is True
        row.update(
            {
                "ground_truth_status": expected_status,
                "ground_truth_bank_ids": sorted(expected_bank_ids),
                "is_correct": actual_match == expected_match
                and (not actual_match or row.get("bank_transaction_id") in expected_bank_ids),
            }
        )
        evaluated.append(row)
    return evaluated


def evaluate_dataset(
    payments_path: str | Path = PAYMENTS_PATH,
    settlements_path: str | Path = SETTLEMENTS_PATH,
    bank_transactions_path: str | Path = BANK_TRANSACTIONS_PATH,
    ground_truth_path: str | Path = GROUND_TRUTH_PATH,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run the real reconciliation engine and calculate all evaluation metrics."""
    output = ReconciliationEngine().reconcile(
        payments_path, settlements_path, bank_transactions_path
    )
    results = normalize_reconciliation_output(output)
    evaluated = compare_with_ground_truth(results, load_ground_truth(ground_truth_path))
    return evaluated, calculate_all_metrics(evaluated)


def print_metrics(metrics: dict[str, Any]) -> None:
    """Print evaluation metrics in a clean terminal format."""
    print("\n" + "=" * 50)
    print("LEDGERPILOT RECONCILIATION EVALUATION")
    print("=" * 50)
    print(f"Total Records       : {metrics['total_records']}")
    print(f"Matched             : {metrics['matched']}")
    print(f"AI Assisted         : {metrics['ai_assisted']}")
    print(f"Human Review        : {metrics['human_review']}")
    print(f"Exceptions          : {metrics['exceptions']}")
    print("-" * 50)
    print(f"Match Rate          : {metrics['match_rate']:.2%}")
    print(f"Exception Rate      : {metrics['exception_rate']:.2%}")
    print(f"Precision           : {metrics['precision']:.2%}")
    print(f"Recall              : {metrics['recall']:.2%}")
    print(f"False Auto-Match    : {metrics['false_auto_match_rate']:.2%}")
    print("=" * 50)


if __name__ == "__main__":
    _, metrics = evaluate_dataset()
    print_metrics(metrics)
