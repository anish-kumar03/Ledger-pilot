"""Generate a deterministic, synthetic reconciliation dataset.

The generated files are intentionally free of real personal or financial data.
Each payment has a corresponding ground-truth row, including the expected
relationship to its settlement and zero, one, or multiple bank transactions.
"""

from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any


SEED = 20260903
RECORD_COUNT = 100
DEFAULT_OUTPUT_DIRECTORY = Path(__file__).parent

MERCHANTS = (
	"Northstar Books",
	"Cedar & Finch Market",
	"Blue Harbor Supplies",
	"Maple Street Cafe",
	"Silverline Software",
	"Bright Orchard Goods",
	"Juniper Home Studio",
	"Redwood Bicycle Co",
)

def _scenario_for(index: int) -> str:
	"""Return the deterministic reconciliation scenario for a payment index."""
	if index < 60:
		return "exact_match"
	if index < 65:
		return "reference_formatting_difference"
	if index < 70:
		return "merchant_spelling_difference"
	if index < 75:
		return "date_offset"
	if index < 80:
		return "processing_fee_difference"
	if index < 88:
		return "missing_bank_transaction"
	if index < 93:
		return "duplicate_transaction"
	if index < 96:
		return "partial_settlement"
	if index < 99:
		return "multiple_possible_bank_candidates"
	return "invalid_malformed_record"


def _status_for(scenario: str) -> str:
	"""Map a generated scenario to the expected reconciliation status."""
	return {
		"exact_match": "matched",
		"reference_formatting_difference": "matched_after_reference_normalization",
		"merchant_spelling_difference": "matched_after_merchant_normalization",
		"date_offset": "matched_with_date_offset",
		"processing_fee_difference": "matched_with_fee_variance",
		"missing_bank_transaction": "missing_bank_transaction",
		"duplicate_transaction": "duplicate_bank_transaction",
		"partial_settlement": "partial_settlement",
		"multiple_possible_bank_candidates": "ambiguous_multiple_bank_candidates",
		"invalid_malformed_record": "invalid_record",
	}[scenario]


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
	"""Write rows to a UTF-8 CSV with a stable column order."""
	with path.open("w", newline="", encoding="utf-8") as csv_file:
		writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
		writer.writeheader()
		writer.writerows(rows)


def generate_dataset(output_directory: Path | str = DEFAULT_OUTPUT_DIRECTORY) -> dict[str, Path]:
	"""Generate 100 payments, settlements, bank transactions, and ground truth.

	The fixed seed makes every output reproducible. Files are written to
	``output_directory`` as ``payments.csv``, ``settlements.csv``,
	``bank_transactions.csv``, and ``ground_truth.csv``. The returned mapping
	contains the paths of all four files.
	"""
	output_path = Path(output_directory)
	output_path.mkdir(parents=True, exist_ok=True)
	rng = random.Random(SEED)
	base_date = date(2026, 1, 5)

	payments: list[dict[str, Any]] = []
	settlements: list[dict[str, Any]] = []
	bank_transactions: list[dict[str, Any]] = []
	ground_truth: list[dict[str, Any]] = []

	for index in range(RECORD_COUNT):
		payment_id = f"PAY-{index + 1:04d}"
		settlement_id = f"SET-{index + 1:04d}"
		bank_id = f"BANK-{index + 1:04d}"
		scenario = _scenario_for(index)
		merchant = MERCHANTS[index % len(MERCHANTS)]
		amount = Decimal(rng.randint(1200, 85000)) / Decimal("100")
		payment_date = base_date + timedelta(days=index)
		reference = f"ORD-{2026}-{index + 1:05d}"
		fee = (amount * Decimal("0.029") + Decimal("0.30")).quantize(Decimal("0.01"))

		payment: dict[str, Any] = {
			"payment_id": payment_id,
			"transaction_reference": reference,
			"merchant_name": merchant,
			"invoice_id": f"INV-{index + 1:05d}",
			"payment_date": payment_date.isoformat(),
			"amount": f"{amount:.2f}",
			"currency": "USD",
		}
		settlement: dict[str, Any] = {
			"settlement_id": settlement_id,
			"payment_id": payment_id,
			"settlement_date": (payment_date + timedelta(days=2)).isoformat(),
			"gross_amount": f"{amount:.2f}",
			"processing_fee": f"{fee:.2f}",
			"net_amount": f"{amount - fee:.2f}",
			"currency": "USD",
		}

		if scenario == "partial_settlement":
			partial_amount = (amount * Decimal("0.60")).quantize(Decimal("0.01"))
			settlement["gross_amount"] = f"{partial_amount:.2f}"
			settlement["net_amount"] = f"{partial_amount - fee:.2f}"

		payments.append(payment)
		settlements.append(settlement)

		linked_bank_ids: list[str] = []
		if scenario != "missing_bank_transaction":
			bank_reference = reference
			bank_merchant = merchant
			bank_date = payment_date
			bank_amount = amount - fee

			if scenario == "reference_formatting_difference":
				bank_reference = reference.replace("-", " ").lower()
			elif scenario == "merchant_spelling_difference":
				bank_merchant = merchant.replace("o", "oo", 1)
			elif scenario == "date_offset":
				bank_date = payment_date + timedelta(days=4)
			elif scenario == "processing_fee_difference":
				bank_amount = amount - fee - Decimal("0.02")

			bank_transactions.append(
				{
					"bank_transaction_id": bank_id,
					"transaction_reference": bank_reference,
					"merchant_name": bank_merchant,
					"transaction_date": bank_date.isoformat(),
					"amount": f"{bank_amount:.2f}",
					"currency": "USD",
					"transaction_type": "credit",
				}
			)
			linked_bank_ids.append(bank_id)

			if scenario == "duplicate_transaction":
				duplicate_id = f"BANK-DUP-{index + 1:04d}"
				duplicate = bank_transactions[-1].copy()
				duplicate["bank_transaction_id"] = duplicate_id
				bank_transactions.append(duplicate)
				linked_bank_ids.append(duplicate_id)
			elif scenario == "multiple_possible_bank_candidates":
				candidate_id = f"BANK-CAND-{index + 1:04d}"
				candidate = bank_transactions[-1].copy()
				candidate["bank_transaction_id"] = candidate_id
				candidate_amount = bank_amount + Decimal("0.01")
				candidate["amount"] = f"{candidate_amount:.2f}"
				bank_transactions.append(candidate)
				linked_bank_ids.append(candidate_id)

		if scenario == "invalid_malformed_record":
			payment["payment_date"] = "not-a-date"
			payment["amount"] = "unknown"
			settlement["gross_amount"] = "N/A"

		ground_truth.append(
			{
				"payment_id": payment_id,
				"settlement_id": settlement_id,
				"bank_transaction_ids": ";".join(linked_bank_ids),
				"expected_status": _status_for(scenario),
				"scenario": scenario,
			}
		)

	paths = {
		"payments": output_path / "payments.csv",
		"settlements": output_path / "settlements.csv",
		"bank_transactions": output_path / "bank_transactions.csv",
		"ground_truth": output_path / "ground_truth.csv",
	}
	_write_csv(paths["payments"], payments, list(payments[0]))
	_write_csv(paths["settlements"], settlements, list(settlements[0]))
	_write_csv(paths["bank_transactions"], bank_transactions, list(bank_transactions[0]))
	_write_csv(paths["ground_truth"], ground_truth, list(ground_truth[0]))
	return paths


if __name__ == "__main__":
	generate_dataset()
