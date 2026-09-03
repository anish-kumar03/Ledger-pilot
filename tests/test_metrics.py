from engine.scorer import ReconciliationScorer


def test_scorer_uses_credit_and_date_aliases():
	"""Credit and date bank aliases produce valid amount and date scores."""
	result = ReconciliationScorer().score(
		{
			"payment_id": "PAY-1",
			"transaction_reference": "payment-ref",
			"merchant_name": "Example Merchant",
		},
		{
			"settlement_date": "2026-09-04",
			"net_amount": "125.00",
		},
		{
			"bank_reference": "bank-ref",
			"credit": "125.00",
			"date": "2026-09-05",
			"merchant_name": "Example Merchant",
		},
	)

	assert result.amount_score == 1.0
	assert result.date_score > 0.0


def _complete_records():
	return (
		{
			"transaction_reference": "REF-1",
			"merchant_name": "Example Merchant",
			"invoice_id": "INV-1",
			"payment_date": "2026-09-04",
		},
		{"settlement_date": "2026-09-04", "net_amount": "125.00"},
		{
			"transaction_reference": "REF-1",
			"merchant_name": "Example Merchant",
			"invoice_id": "INV-1",
			"transaction_date": "2026-09-04",
			"amount": "125.00",
		},
	)


def test_all_available_signals_use_configured_weights():
	result = ReconciliationScorer().score(*_complete_records())

	assert result.overall_score == 1.0


def test_missing_invoice_is_excluded_from_weighted_average():
	payment, settlement, bank = _complete_records()
	del bank["invoice_id"]

	result = ReconciliationScorer().score(payment, settlement, bank)

	assert result.invoice_score == 0.0
	assert result.overall_score == 1.0
	assert "invoice_missing_or_unavailable" in result.explanation_codes


def test_missing_merchant_is_excluded_from_weighted_average():
	payment, settlement, bank = _complete_records()
	del bank["merchant_name"]

	result = ReconciliationScorer().score(payment, settlement, bank)

	assert result.overall_score == 1.0
	assert "merchant_missing_or_unavailable" in result.explanation_codes


def test_missing_amount_is_excluded_from_weighted_average():
	payment, settlement, bank = _complete_records()
	del bank["amount"]

	result = ReconciliationScorer().score(payment, settlement, bank)

	assert result.overall_score == 1.0
	assert "amount_missing_or_unavailable" in result.explanation_codes


def test_all_signals_missing_returns_zero_score():
	result = ReconciliationScorer().score({}, {}, {})

	assert result.overall_score == 0.0
	assert all("missing_or_unavailable" in code for code in result.explanation_codes)
