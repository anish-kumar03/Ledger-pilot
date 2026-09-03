"""End-to-end deterministic reconciliation orchestration."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from ai.agent import ReconciliationAgent
from engine.matcher import CandidateMatch, generate_candidates
from engine.normalizer import (
	normalize_date,
	normalize_invoice_id,
	normalize_merchant_name,
	normalize_monetary_value,
	normalize_transaction_reference,
)
from engine.policy import PolicyDecision, PolicyEngine, PolicyResult, PolicyThresholds
from engine.scorer import ReconciliationScore, ReconciliationScorer, ScoringWeights


Record = Mapping[str, Any]


class AuditEvent(BaseModel):
	"""Immutable audit evidence for one processed payment record."""

	model_config = ConfigDict(frozen=True)

	event_id: str
	created_at: datetime
	payment_id: str | None = None
	decision: str
	reason_codes: list[str] = Field(default_factory=list)
	evidence: dict[str, Any] = Field(default_factory=dict)


class ReconciliationOutput(BaseModel):
	"""Complete result buckets and audit events for a reconciliation run."""

	matches: list[dict[str, Any]] = Field(default_factory=list)
	ai_assisted_decisions: list[dict[str, Any]] = Field(default_factory=list)
	human_review_cases: list[dict[str, Any]] = Field(default_factory=list)
	exceptions: list[dict[str, Any]] = Field(default_factory=list)
	audit_events: list[AuditEvent] = Field(default_factory=list)


def _records(source: pd.DataFrame | Iterable[Record] | str | Path) -> list[dict[str, Any]]:
	"""Load a DataFrame, record iterable, or CSV path into record dictionaries."""
	if isinstance(source, (str, Path)):
		return pd.read_csv(source).to_dict(orient="records")
	if isinstance(source, pd.DataFrame):
		return source.to_dict(orient="records")
	return [dict(record) for record in source]


def _normalized(record: Record) -> dict[str, Any]:
	"""Add canonical values while retaining the original source fields."""
	result = dict(record)
	if "transaction_reference" in result:
		result["normalized_transaction_reference"] = normalize_transaction_reference(
			result["transaction_reference"]
		)
	if "merchant_name" in result:
		result["normalized_merchant_name"] = normalize_merchant_name(result["merchant_name"])
	if "invoice_id" in result:
		result["normalized_invoice_id"] = normalize_invoice_id(result["invoice_id"])
	for field in ("payment_date", "settlement_date", "transaction_date"):
		if field in result:
			parsed = normalize_date(result[field])
			result[f"normalized_{field}"] = parsed.isoformat() if parsed else None
	for field in ("amount", "gross_amount", "processing_fee", "net_amount"):
		if field in result:
			parsed = normalize_monetary_value(result[field])
			result[f"normalized_{field}"] = str(parsed) if parsed is not None else None
	return result


class ReconciliationEngine:
	"""Run deterministic reconciliation and isolate failures per payment."""

	def __init__(
		self,
		policy_thresholds: PolicyThresholds | Mapping[str, Any] | None = None,
		scoring_weights: ScoringWeights | Mapping[str, float] | None = None,
		ai_agent: ReconciliationAgent | None = None,
	) -> None:
		"""Configure deterministic policy, scoring, and optional AI reasoning."""
		self.policy = PolicyEngine(policy_thresholds)
		self.scorer = ReconciliationScorer(scoring_weights)
		self.ai_agent = ai_agent or ReconciliationAgent()

	def reconcile(
		self,
		payments: pd.DataFrame | Iterable[Record] | str | Path,
		settlements: pd.DataFrame | Iterable[Record] | str | Path,
		bank_transactions: pd.DataFrame | Iterable[Record] | str | Path,
	) -> ReconciliationOutput:
		"""Process every payment and return result buckets with audit evidence."""
		payment_records = [_normalized(record) for record in _records(payments)]
		settlement_records = [_normalized(record) for record in _records(settlements)]
		bank_records = [_normalized(record) for record in _records(bank_transactions)]
		settlement_by_payment = {
			str(record["payment_id"]): record
			for record in settlement_records
			if record.get("payment_id") is not None
		}
		output = ReconciliationOutput()

		for payment in payment_records:
			payment_id = str(payment.get("payment_id")) if payment.get("payment_id") else None
			try:
				if payment_id is None:
					raise ValueError("missing_payment_id")
				settlement = settlement_by_payment.get(payment_id)
				candidates = generate_candidates([payment], [settlement] if settlement else [], bank_records)
				candidate_records = [candidate.model_dump() for candidate in candidates]
				if not candidates:
					result = PolicyResult(
						decision=PolicyDecision.EXCEPTION,
						policy_reasons=["No viable bank candidate was generated"],
						blocked_conditions=["missing_source_record"],
					)
					self._append(output, "exceptions", payment, result, candidate_records)
					continue

				bank_by_id = {str(record.get("bank_transaction_id")): record for record in bank_records}
				scored: list[tuple[CandidateMatch, ReconciliationScore]] = []
				for candidate in candidates:
					bank = bank_by_id[str(candidate.bank_transaction_id)]
					scored.append((candidate, self.scorer.score(payment, settlement or {}, bank)))
				best_candidate, best_score = max(scored, key=lambda item: item[1].overall_score)
				policy_inputs = [
					{**candidate.model_dump(), **score.model_dump()}
					for candidate, score in scored
				]
				policy_result = self.policy.evaluate_one(policy_inputs[0])
				if len(policy_inputs) > 1:
					policy_result = self.policy.evaluate(policy_inputs)[0]
				policy_input = {**best_candidate.model_dump(), **best_score.model_dump()}

				if policy_result.decision is PolicyDecision.AI_REVIEW:
					ai_result = self.ai_agent.reason(
						payment,
						settlement,
						[bank_by_id[str(candidate.bank_transaction_id)] for candidate in candidates],
						{"candidate": best_candidate.model_dump(), "score": best_score.model_dump()},
					)
					policy_result = self.policy.finalize_ai(
						policy_result, ai_result.model_dump()
					)
					final_bucket = {
						PolicyDecision.AUTO_MATCH: "matches",
						PolicyDecision.HUMAN_REVIEW: "human_review_cases",
						PolicyDecision.EXCEPTION: "exceptions",
						PolicyDecision.AI_REVIEW: "human_review_cases",
					}[policy_result.decision]
					entry = {**policy_input, "ai_decision": ai_result.model_dump()}
					self._append(output, final_bucket, payment, policy_result, [
						{**candidate.model_dump(), **score.model_dump()}
						for candidate, score in scored
					])
					output.ai_assisted_decisions.append(entry)
				else:
					bucket = {
						PolicyDecision.AUTO_MATCH: "matches",
						PolicyDecision.HUMAN_REVIEW: "human_review_cases",
						PolicyDecision.EXCEPTION: "exceptions",
						PolicyDecision.AI_REVIEW: "human_review_cases",
					}[policy_result.decision]
					self._append(output, bucket, payment, policy_result, [policy_input])
			except Exception as error:
				result = PolicyResult(
					decision=PolicyDecision.EXCEPTION,
					policy_reasons=["Record processing failed"],
					blocked_conditions=[str(error) or "processing_error"],
				)
				self._append(output, "exceptions", payment, result, [])
		return output

	@staticmethod
	def _append(
		output: ReconciliationOutput,
		bucket: str,
		payment: Record,
		result: PolicyResult,
		evidence: list[dict[str, Any]],
	) -> None:
		"""Append a result and exactly one audit event for a payment."""
		entry = {
			"payment_id": payment.get("payment_id"),
			"decision": result.decision.value,
			"policy_reasons": result.policy_reasons,
			"blocked_conditions": result.blocked_conditions,
			"evidence": evidence,
		}
		getattr(output, bucket).append(entry)
		output.audit_events.append(
			AuditEvent(
					event_id=f"AUDIT-{len(output.audit_events) + 1:06d}",
				created_at=datetime.now(timezone.utc),
				payment_id=(str(payment["payment_id"]) if payment.get("payment_id") else None),
				decision=result.decision.value,
				reason_codes=result.blocked_conditions or result.policy_reasons,
				evidence={"candidate_count": len(evidence), "records": evidence},
			)
		)


def reconcile(
	payments: pd.DataFrame | Iterable[Record] | str | Path,
	settlements: pd.DataFrame | Iterable[Record] | str | Path,
	bank_transactions: pd.DataFrame | Iterable[Record] | str | Path,
	**kwargs: Any,
) -> ReconciliationOutput:
	"""Convenience wrapper for :class:`ReconciliationEngine`."""
	return ReconciliationEngine(**kwargs).reconcile(payments, settlements, bank_transactions)
