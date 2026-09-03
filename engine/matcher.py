"""Deterministic candidate generation for payment reconciliation."""

from __future__ import annotations

from datetime import date
from datetime import timedelta
from typing import Any, Iterable, Mapping

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field
from rapidfuzz.fuzz import token_set_ratio

from engine.normalizer import (
	normalize_date,
	normalize_invoice_id,
	normalize_merchant_name,
	normalize_monetary_value,
	normalize_transaction_reference,
)


class CandidateMatch(BaseModel):
	"""A ranked, evidence-backed candidate without a final decision."""

	model_config = ConfigDict(frozen=True)

	payment_id: str
	settlement_id: str | None = None
	bank_transaction_id: str
	match_score: float = Field(ge=0.0, le=1.0)
	matching_signals: list[str] = Field(default_factory=list)
	candidate_rank: int = Field(ge=1)


Record = Mapping[str, Any]
Records = pd.DataFrame | Iterable[Record]

BANK_AMOUNT_FIELDS = ("amount", "net_amount", "credit", "credit_amount")
BANK_DATE_FIELDS = ("transaction_date", "date", "bank_date", "settlement_date")
BANK_REFERENCE_FIELDS = (
	"transaction_reference",
	"reference",
	"bank_reference",
	"description",
)


def _records(source: Records) -> list[dict[str, Any]]:
	"""Convert supported tabular inputs into independent record dictionaries."""
	if isinstance(source, pd.DataFrame):
		return source.to_dict(orient="records")
	return [dict(record) for record in source]


def _value(record: Record, *names: str) -> Any:
	"""Return the first non-null field from a record."""
	for name in names:
		if name in record and record[name] is not None:
			return record[name]
	return None


def _amount(record: Record) -> Any:
	"""Read the amount most appropriate for a settlement or bank record."""
	return normalize_monetary_value(_value(record, *BANK_AMOUNT_FIELDS))


def _same_amount(left: Any, right: Any) -> bool:
	"""Compare normalized monetary values without floating-point arithmetic."""
	left_amount = normalize_monetary_value(left)
	right_amount = normalize_monetary_value(right)
	return left_amount is not None and left_amount == right_amount


def _within_date_tolerance(left: Any, right: Any, tolerance: timedelta) -> bool:
	"""Return whether two valid dates are no farther apart than ``tolerance``."""
	left_date = normalize_date(left)
	right_date = normalize_date(right)
	return (
		left_date is not None
		and right_date is not None
		and abs(left_date - right_date) <= tolerance
	)


def _merchant_similarity(left: Any, right: Any) -> float | None:
	"""Return normalized merchant similarity as a value between zero and one."""
	left_name = normalize_merchant_name(left)
	right_name = normalize_merchant_name(right)
	if left_name is None or right_name is None:
		return None
	return token_set_ratio(left_name, right_name) / 100.0


class ReconciliationMatcher:
	"""Generate deterministic payment-to-bank candidates in four stages."""

	def __init__(
		self,
		date_tolerance_days: int = 3,
		merchant_similarity_threshold: float = 0.80,
	) -> None:
		"""Configure date tolerance and the minimum merchant similarity."""
		if date_tolerance_days < 0:
			raise ValueError("date_tolerance_days must be non-negative")
		if not 0.0 <= merchant_similarity_threshold <= 1.0:
			raise ValueError("merchant_similarity_threshold must be between 0 and 1")
		self.date_tolerance = timedelta(days=date_tolerance_days)
		self.merchant_similarity_threshold = merchant_similarity_threshold

	def match(
		self,
		payments: Records,
		settlements: Records,
		bank_transactions: Records,
	) -> list[CandidateMatch]:
		"""Return ranked candidates for all payment and settlement records.

		Candidate generation stops at the first stage that produces candidates
		for a payment. This preserves stage precedence while retaining every
		bank candidate found within that stage. No candidate is accepted or
		rejected here; that remains the responsibility of the policy layer.
		"""
		payment_records = _records(payments)
		settlement_by_payment = {
			str(record.get("payment_id")): record
			for record in _records(settlements)
			if record.get("payment_id") is not None
		}
		bank_records = _records(bank_transactions)
		results: list[CandidateMatch] = []

		for payment in payment_records:
			payment_id = payment.get("payment_id")
			if payment_id is None:
				continue
			payment_id = str(payment_id)
			settlement = settlement_by_payment.get(payment_id, {})
			stage_candidates = self._candidates_for_stage(
				payment, settlement, bank_records, stage=1
			)
			if not stage_candidates:
				stage_candidates = self._candidates_for_stage(
					payment, settlement, bank_records, stage=2
				)
			if not stage_candidates:
				stage_candidates = self._candidates_for_stage(
					payment, settlement, bank_records, stage=3
				)
			if not stage_candidates:
				stage_candidates = self._candidates_for_stage(
					payment, settlement, bank_records, stage=4
				)

			stage_candidates.sort(
				key=lambda candidate: (-candidate.match_score, candidate.bank_transaction_id)
			)
			results.extend(
				candidate.model_copy(update={"candidate_rank": rank})
				for rank, candidate in enumerate(stage_candidates, start=1)
			)
		return results

	def _candidates_for_stage(
		self,
		payment: Record,
		settlement: Record,
		bank_records: list[Record],
		stage: int,
	) -> list[CandidateMatch]:
		"""Build candidates satisfying one matching stage."""
		candidates: list[CandidateMatch] = []
		payment_reference = normalize_transaction_reference(
			_value(payment, *BANK_REFERENCE_FIELDS)
		)
		settlement_amount = _amount(settlement)
		settlement_date = _value(settlement, "settlement_date")
		payment_invoice = normalize_invoice_id(payment.get("invoice_id"))
		payment_merchant = payment.get("merchant_name")
		raw_payment_reference = _value(payment, *BANK_REFERENCE_FIELDS)

		for bank in bank_records:
			bank_id = bank.get("bank_transaction_id")
			if bank_id is None:
				continue
			signals: list[str] = []
			score = 0.0
			bank_reference = normalize_transaction_reference(
				_value(bank, *BANK_REFERENCE_FIELDS)
			)
			raw_bank_reference = _value(bank, *BANK_REFERENCE_FIELDS)

			if (
				stage == 1
				and raw_payment_reference is not None
				and raw_payment_reference == raw_bank_reference
			):
				signals.append("exact_reference")
				score = 1.0
			elif stage == 2:
				if (
					payment_reference is not None
					and payment_reference == bank_reference
					and raw_payment_reference != raw_bank_reference
				):
					signals.append("normalized_reference")
					score = 0.95
			elif stage == 3 and _same_amount(settlement_amount, _amount(bank)):
				if _within_date_tolerance(
					settlement_date,
					_value(bank, *BANK_DATE_FIELDS),
					self.date_tolerance,
				):
					signals.extend(("exact_amount", "date_within_tolerance"))
					score = 0.85
			elif stage == 4:
				bank_invoice = normalize_invoice_id(bank.get("invoice_id"))
				merchant_score = _merchant_similarity(payment_merchant, bank.get("merchant_name"))
				if (
					payment_invoice is not None
					and payment_invoice == bank_invoice
					and merchant_score is not None
					and merchant_score >= self.merchant_similarity_threshold
				):
					signals.extend(("exact_invoice", "merchant_similarity"))
					score = 0.70 + (merchant_score * 0.20)

			if signals:
				candidates.append(
					CandidateMatch(
						payment_id=str(payment["payment_id"]),
						settlement_id=(
							str(settlement["settlement_id"])
							if settlement.get("settlement_id") is not None
							else None
						),
						bank_transaction_id=str(bank_id),
						match_score=round(score, 6),
						matching_signals=signals,
						candidate_rank=1,
					)
				)
		return candidates


def generate_candidates(
	payments: Records,
	settlements: Records,
	bank_transactions: Records,
	*,
	date_tolerance_days: int = 3,
	merchant_similarity_threshold: float = 0.80,
) -> list[CandidateMatch]:
	"""Convenience wrapper for deterministic candidate generation."""
	matcher = ReconciliationMatcher(
		date_tolerance_days=date_tolerance_days,
		merchant_similarity_threshold=merchant_similarity_threshold,
	)
	return matcher.match(payments, settlements, bank_transactions)
