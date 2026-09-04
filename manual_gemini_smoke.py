"""Manual Gemini smoke test for local development.

Run with ``GEMINI_API_KEY`` set in the environment. The key is never printed.
"""

from ai.agent import ReconciliationAgent


def main() -> None:
	"""Send one ambiguous synthetic case to the configured Gemini model."""
	result = ReconciliationAgent().reason(
		payment={
			"payment_id": "PAY-SMOKE-001",
			"transaction_reference": "ORD-2026-AMB-001",
			"merchant_name": "Northstar Books",
			"invoice_id": "INV-SMOKE-001",
			"payment_date": "2026-09-04",
		},
		settlement={
			"settlement_id": "SET-SMOKE-001",
			"net_amount": "604.27",
			"settlement_date": "2026-09-06",
		},
		bank_candidates=[
			{
				"bank_transaction_id": "BANK-SMOKE-001",
				"transaction_reference": "ORD-2026-AMB-001",
				"merchant_name": "Northstar Bookstore",
				"amount": "604.27",
				"transaction_date": "2026-09-07",
			},
			{
				"bank_transaction_id": "BANK-SMOKE-002",
				"transaction_reference": "ORD-2026-AMB-001",
				"merchant_name": "North Star Books",
				"amount": "604.25",
				"transaction_date": "2026-09-06",
			},
		],
		deterministic_evidence={
			"reason": "Two plausible bank candidates require evidence-only review"
		},
	)
	print(result.model_dump_json(indent=2))
	print(f"selected_bank_transaction_id: {result.selected_bank_transaction_id}")
	print(f"confidence: {result.confidence}")
	print(f"reason_codes: {result.reason_codes}")
	print(f"explanation: {result.explanation}")


if __name__ == "__main__":
	main()