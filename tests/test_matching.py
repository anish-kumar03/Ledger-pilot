import pytest

from engine.matcher import ReconciliationMatcher


@pytest.mark.parametrize("amount_field", ["amount", "credit", "net_amount"])
def test_bank_amount_alias_generates_amount_candidate(amount_field):
	"""Bank amount aliases are used by the exact amount/date stage."""
	payment = {
		"payment_id": "PAY-1",
		"transaction_reference": "payment-ref",
		"merchant_name": "Example Merchant",
	}
	settlement = {
		"settlement_id": "SET-1",
		"payment_id": "PAY-1",
		"settlement_date": "2026-09-04",
		"net_amount": "125.00",
	}
	bank = {
		"bank_transaction_id": "BANK-1",
		"transaction_reference": "different-ref",
		amount_field: "125.00",
		"transaction_date": "2026-09-04",
	}

	matches = ReconciliationMatcher().match([payment], [settlement], [bank])

	assert len(matches) == 1
	assert matches[0].matching_signals == ["exact_amount", "date_within_tolerance"]


def test_bank_date_alias_generates_date_candidate():
	"""The date alias is used when transaction_date is absent."""
	payment = {
		"payment_id": "PAY-1",
		"transaction_reference": "payment-ref",
	}
	settlement = {
		"settlement_id": "SET-1",
		"payment_id": "PAY-1",
		"settlement_date": "2026-09-04",
		"net_amount": "125.00",
	}
	bank = {
		"bank_transaction_id": "BANK-1",
		"reference": "different-ref",
		"amount": "125.00",
		"date": "2026-09-05",
	}

	matches = ReconciliationMatcher().match([payment], [settlement], [bank])

	assert len(matches) == 1
	assert "date_within_tolerance" in matches[0].matching_signals
