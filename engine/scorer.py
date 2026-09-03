"""Deterministic weighted scoring for reconciliation candidates."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator
from rapidfuzz.fuzz import ratio, token_set_ratio

from engine.normalizer import (
	normalize_date,
	normalize_invoice_id,
	normalize_merchant_name,
	normalize_monetary_value,
	normalize_transaction_reference,
)


DEFAULT_WEIGHTS: dict[str, float] = {
	"reference": 0.30,
	"amount": 0.25,
	"date": 0.15,
	"merchant": 0.15,
	"invoice": 0.15,
}


class SignalScores(BaseModel):
	"""Individual deterministic scores for each reconciliation signal."""

	model_config = ConfigDict(frozen=True)

	reference_score: float = Field(ge=0.0, le=1.0)
	amount_score: float = Field(ge=0.0, le=1.0)
	date_score: float = Field(ge=0.0, le=1.0)
	merchant_score: float = Field(ge=0.0, le=1.0)
	invoice_score: float = Field(ge=0.0, le=1.0)


class ReconciliationScore(SignalScores):
	"""Weighted reconciliation score and its human-readable explanation codes."""

	overall_score: float = Field(ge=0.0, le=1.0)
	explanation_codes: list[str] = Field(default_factory=list)


class ScoringWeights(BaseModel):
	"""Configurable weights for the five reconciliation signals."""

	model_config = ConfigDict(frozen=True)

	reference: float = Field(default=DEFAULT_WEIGHTS["reference"], ge=0.0)
	amount: float = Field(default=DEFAULT_WEIGHTS["amount"], ge=0.0)
	date: float = Field(default=DEFAULT_WEIGHTS["date"], ge=0.0)
	merchant: float = Field(default=DEFAULT_WEIGHTS["merchant"], ge=0.0)
	invoice: float = Field(default=DEFAULT_WEIGHTS["invoice"], ge=0.0)

	@field_validator("invoice")
	@classmethod
	def validate_total(cls, value: float, info: Any) -> float:
		"""Require a positive total weight after the final field is supplied."""
		weights = dict(info.data)
		weights["invoice"] = value
		if sum(weights.values()) <= 0.0:
			raise ValueError("at least one scoring weight must be positive")
		return value


Record = Mapping[str, Any]

BANK_AMOUNT_FIELDS = ("amount", "net_amount", "credit", "credit_amount")
BANK_DATE_FIELDS = ("transaction_date", "date", "bank_date", "settlement_date")
BANK_REFERENCE_FIELDS = (
	"transaction_reference",
	"reference",
	"bank_reference",
	"description",
)


def _field(record: Record, *names: str) -> Any:
	"""Return the first non-null value from a record."""
	for name in names:
		if name in record and record[name] is not None:
			return record[name]
	return None


def _text_score(left: Any, right: Any, normalizer: Any, fuzzy: Any = ratio) -> float:
	"""Compare two normalized text values, returning zero for missing values."""
	left_value = normalizer(left)
	right_value = normalizer(right)
	if left_value is None or right_value is None:
		return 0.0
	return fuzzy(left_value, right_value) / 100.0


def _amount_score(expected: Any, actual: Any) -> float:
	"""Score monetary closeness relative to the expected amount."""
	expected_amount = normalize_monetary_value(expected)
	actual_amount = normalize_monetary_value(actual)
	if expected_amount is None or actual_amount is None:
		return 0.0
	if expected_amount == actual_amount:
		return 1.0
	baseline = max(abs(expected_amount), Decimal("0.01"))
	difference = abs(expected_amount - actual_amount)
	return max(0.0, float(Decimal(1) - (difference / baseline)))


def _date_score(expected: Any, actual: Any, tolerance_days: int) -> float:
	"""Score date proximity linearly within the configured tolerance window."""
	expected_date = normalize_date(expected)
	actual_date = normalize_date(actual)
	if expected_date is None or actual_date is None:
		return 0.0
	distance = abs(expected_date - actual_date).days
	if distance == 0:
		return 1.0
	if tolerance_days == 0 or distance > tolerance_days:
		return 0.0
	return max(0.0, 1.0 - (distance / tolerance_days))


def _explanations(
	scores: SignalScores,
	available: Mapping[str, bool],
	payment: Record,
	settlement: Record,
	bank: Record,
	date_tolerance_days: int,
) -> list[str]:
	"""Produce stable codes describing strengths and missing comparison data."""
	codes: list[str] = []
	if not available["reference"]:
		codes.append("reference_missing_or_unavailable")
	elif scores.reference_score == 1.0:
		codes.append("reference_exact")
	elif scores.reference_score > 0.0:
		codes.append("reference_similar")
	else:
		codes.append("reference_mismatch")
	if not available["amount"]:
		codes.append("amount_missing_or_unavailable")
	elif scores.amount_score == 1.0:
		codes.append("amount_exact")
	elif scores.amount_score > 0.0:
		codes.append("amount_within_variance")
	else:
		codes.append("amount_mismatch")
	if not available["date"]:
		codes.append("date_missing_or_unavailable")
	elif scores.date_score == 1.0:
		codes.append("date_exact")
	elif scores.date_score > 0.0:
		codes.append("date_within_tolerance")
	else:
		codes.append("date_outside_tolerance")
	if not available["merchant"]:
		codes.append("merchant_missing_or_unavailable")
	elif scores.merchant_score == 1.0:
		codes.append("merchant_exact")
	elif scores.merchant_score > 0.0:
		codes.append("merchant_similar")
	else:
		codes.append("merchant_mismatch")
	if not available["invoice"]:
		codes.append("invoice_missing_or_unavailable")
	elif scores.invoice_score == 1.0:
		codes.append("invoice_exact")
	elif scores.invoice_score > 0.0:
		codes.append("invoice_similar")
	else:
		codes.append("invoice_mismatch")
	return codes


class ReconciliationScorer:
	"""Calculate deterministic weighted scores for payment candidates."""

	def __init__(
		self,
		weights: ScoringWeights | Mapping[str, float] | None = None,
		date_tolerance_days: int = 3,
	) -> None:
		"""Configure signal weights and the date proximity tolerance."""
		if date_tolerance_days < 0:
			raise ValueError("date_tolerance_days must be non-negative")
		self.weights = weights if isinstance(weights, ScoringWeights) else ScoringWeights(**(dict(weights) if weights else {}))
		self.date_tolerance = timedelta(days=date_tolerance_days)
		self.date_tolerance_days = date_tolerance_days

	def score(
		self,
		payment: Record,
		settlement: Record,
		bank_transaction: Record,
	) -> ReconciliationScore:
		"""Return per-signal scores, a weighted overall score, and explanation codes."""
		reference_score = _text_score(
			_field(payment, "transaction_reference"),
			_field(bank_transaction, *BANK_REFERENCE_FIELDS),
			normalize_transaction_reference,
		)
		amount_score = _amount_score(
			_field(settlement, "net_amount", "amount"),
			_field(bank_transaction, *BANK_AMOUNT_FIELDS),
		)
		date_score = _date_score(
			_field(payment, "payment_date") or _field(settlement, "settlement_date"),
			_field(bank_transaction, *BANK_DATE_FIELDS),
			self.date_tolerance_days,
		)
		merchant_score = _text_score(
			_field(payment, "merchant_name"),
			_field(bank_transaction, "merchant_name"),
			normalize_merchant_name,
			token_set_ratio,
		)
		invoice_score = _text_score(
			_field(payment, "invoice_id"),
			_field(bank_transaction, "invoice_id"),
			normalize_invoice_id,
		)
		available = {
			"reference": normalize_transaction_reference(
				_field(payment, "transaction_reference")
			) is not None
			and normalize_transaction_reference(
				_field(bank_transaction, *BANK_REFERENCE_FIELDS)
			) is not None,
			"amount": normalize_monetary_value(
				_field(settlement, "net_amount", "amount")
			) is not None
			and normalize_monetary_value(
				_field(bank_transaction, *BANK_AMOUNT_FIELDS)
			) is not None,
			"date": normalize_date(
				_field(payment, "payment_date") or _field(settlement, "settlement_date")
			) is not None
			and normalize_date(_field(bank_transaction, *BANK_DATE_FIELDS)) is not None,
			"merchant": normalize_merchant_name(
				_field(payment, "merchant_name")
			) is not None
			and normalize_merchant_name(_field(bank_transaction, "merchant_name")) is not None,
			"invoice": normalize_invoice_id(
				_field(payment, "invoice_id")
			) is not None
			and normalize_invoice_id(_field(bank_transaction, "invoice_id")) is not None,
		}
		scores = SignalScores(
			reference_score=round(reference_score, 6),
			amount_score=round(amount_score, 6),
			date_score=round(date_score, 6),
			merchant_score=round(merchant_score, 6),
			invoice_score=round(invoice_score, 6),
		)
		weights = self.weights
		total_weight = weights.reference + weights.amount + weights.date + weights.merchant + weights.invoice
		weighted_scores = {
			"reference": (scores.reference_score, weights.reference),
			"amount": (scores.amount_score, weights.amount),
			"date": (scores.date_score, weights.date),
			"merchant": (scores.merchant_score, weights.merchant),
			"invoice": (scores.invoice_score, weights.invoice),
		}
		available_weight = sum(
			weight for signal, (_, weight) in weighted_scores.items() if available[signal]
		)
		weighted_total = sum(
		score * weight
		for signal, (score, weight) in weighted_scores.items()
		if available[signal]
		)
		overall_score = weighted_total / available_weight if available_weight else 0.0
		return ReconciliationScore(
			**scores.model_dump(),
			overall_score=round(overall_score, 6),
			explanation_codes=_explanations(
				scores, available, payment, settlement, bank_transaction, self.date_tolerance_days
			),
		)


def score_candidate(
	payment: Record,
	settlement: Record,
	bank_transaction: Record,
	*,
	weights: ScoringWeights | Mapping[str, float] | None = None,
	date_tolerance_days: int = 3,
) -> ReconciliationScore:
	"""Convenience wrapper for scoring one reconciliation candidate."""
	return ReconciliationScorer(
		weights=weights,
		date_tolerance_days=date_tolerance_days,
	).score(payment, settlement, bank_transaction)
