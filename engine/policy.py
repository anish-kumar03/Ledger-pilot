"""Deterministic policy decisions for reconciliation candidates."""

from __future__ import annotations

from collections import Counter, defaultdict
from enum import Enum
from typing import Any, Iterable, Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PolicyDecision(str, Enum):
	"""Actions the reconciliation system is allowed to take."""

	AUTO_MATCH = "AUTO_MATCH"
	AI_REVIEW = "AI_REVIEW"
	HUMAN_REVIEW = "HUMAN_REVIEW"
	EXCEPTION = "EXCEPTION"


class PolicyThresholds(BaseModel):
	"""Configurable score and variance thresholds used by the policy engine."""

	model_config = ConfigDict(frozen=True)

	auto_match_score: float = Field(default=0.95, ge=0.0, le=1.0)
	ai_review_score: float = Field(default=0.85, ge=0.0, le=1.0)
	amount_variance_tolerance: float = Field(default=0.01, ge=0.0)

	@model_validator(mode="after")
	def validate_score_order(self) -> "PolicyThresholds":
		"""Ensure the automatic threshold is not below the review threshold."""
		if self.auto_match_score < self.ai_review_score:
			raise ValueError("auto_match_score must be at least ai_review_score")
		return self


class PolicyCandidate(BaseModel):
	"""Candidate fields consumed by policy, including optional scorer evidence."""

	model_config = ConfigDict(extra="ignore", frozen=True)

	payment_id: str
	settlement_id: str | None = None
	bank_transaction_id: str | None = None
	match_score: float = Field(ge=0.0, le=1.0)
	overall_score: float | None = Field(default=None, ge=0.0, le=1.0)
	amount_score: float | None = Field(default=None, ge=0.0, le=1.0)
	amount_variance: float | None = Field(default=None, ge=0.0)
	matching_signals: list[str] = Field(default_factory=list)
	candidate_rank: int = Field(default=1, ge=1)

	@property
	def score(self) -> float:
		"""Return the aggregate scorer value, falling back to matcher score."""
		return self.overall_score if self.overall_score is not None else self.match_score


class PolicyResult(BaseModel):
	"""A policy decision and the deterministic reasons behind it."""

	model_config = ConfigDict(frozen=True)

	decision: PolicyDecision
	policy_reasons: list[str] = Field(default_factory=list)
	blocked_conditions: list[str] = Field(default_factory=list)


CandidateInput = PolicyCandidate | Mapping[str, Any]


class PolicyEngine:
	"""Evaluate candidate reconciliation results without changing their data."""

	def __init__(self, thresholds: PolicyThresholds | Mapping[str, Any] | None = None) -> None:
		"""Configure all policy thresholds."""
		self.thresholds = (
			thresholds
			if isinstance(thresholds, PolicyThresholds)
			else PolicyThresholds(**(dict(thresholds) if thresholds else {}))
		)

	def evaluate(self, candidates: Iterable[CandidateInput]) -> list[PolicyResult]:
		"""Return one deterministic policy result per payment represented.

		Candidates are grouped by payment ID. Multiple viable candidates, duplicate
		bank IDs, missing source IDs, and amount variance are evaluated before score
		bands, ensuring blockers cannot be auto-matched accidentally.
		"""
		normalized = [
			candidate
			if isinstance(candidate, PolicyCandidate)
			else PolicyCandidate.model_validate(candidate)
			for candidate in candidates
		]
		by_payment: dict[str, list[PolicyCandidate]] = defaultdict(list)
		for candidate in normalized:
			by_payment[candidate.payment_id].append(candidate)

		results: list[PolicyResult] = []
		for payment_id, payment_candidates in by_payment.items():
			duplicate_bank_ids = {
				bank_id
				for bank_id, count in Counter(
					candidate.bank_transaction_id for candidate in payment_candidates
				).items()
				if bank_id is not None and count > 1
			}
			blocked: list[str] = []
			reasons: list[str] = []

			if any(
				candidate.settlement_id is None or candidate.bank_transaction_id is None
				for candidate in payment_candidates
			):
				blocked.append("missing_source_record")
				reasons.append("A required settlement or bank transaction record is missing")
			if len(payment_candidates) > 1:
				blocked.append("multiple_viable_candidates")
				reasons.append("More than one candidate is available for the payment")
			if duplicate_bank_ids or any(
				"duplicate" in signal.lower()
				for candidate in payment_candidates
				for signal in candidate.matching_signals
			):
				blocked.append("duplicate_candidate")
				reasons.append("A duplicate bank candidate was detected")

			best = max(payment_candidates, key=lambda candidate: candidate.score)
			variance = best.amount_variance
			if variance is None and best.amount_score is not None:
				variance = 0.0 if best.amount_score >= 1.0 else 1.0 - best.amount_score
			if variance is not None and variance > self.thresholds.amount_variance_tolerance:
				blocked.append("amount_variance_above_tolerance")
				reasons.append("Amount variance exceeds the configured tolerance")

			if "missing_source_record" in blocked:
				decision = PolicyDecision.EXCEPTION
			elif blocked:
				decision = PolicyDecision.HUMAN_REVIEW
			elif best.score >= self.thresholds.auto_match_score:
				decision = PolicyDecision.AUTO_MATCH
				reasons.append("Score meets the automatic-match threshold")
			elif best.score >= self.thresholds.ai_review_score:
				decision = PolicyDecision.AI_REVIEW
				reasons.append("Score is within the AI-review band")
			else:
				decision = PolicyDecision.HUMAN_REVIEW
				reasons.append("Score is below the AI-review threshold")

			results.append(
				PolicyResult(
					decision=decision,
					policy_reasons=reasons,
					blocked_conditions=blocked,
				)
			)
		return results

	def evaluate_one(self, candidate: CandidateInput) -> PolicyResult:
		"""Evaluate one candidate and return its sole policy result."""
		return self.evaluate([candidate])[0]

	def finalize_ai(
		self,
		deterministic_result: PolicyResult,
		ai_decision: Mapping[str, Any],
		*,
		deterministic_score: float | None = None,
		candidate_ids: set[str] | None = None,
	) -> PolicyResult:
		"""Apply deterministic policy to a validated AI recommendation.

		AI confidence can never replace deterministic auto-match eligibility.
		"""
		if deterministic_result.blocked_conditions:
			if "missing_source_record" in deterministic_result.blocked_conditions:
				return PolicyResult(
					decision=PolicyDecision.EXCEPTION,
					policy_reasons=deterministic_result.policy_reasons,
					blocked_conditions=deterministic_result.blocked_conditions,
				)
			return PolicyResult(
				decision=PolicyDecision.HUMAN_REVIEW,
				policy_reasons=deterministic_result.policy_reasons,
				blocked_conditions=deterministic_result.blocked_conditions,
			)
		decision = ai_decision.get("decision")
		confidence = ai_decision.get("confidence", 0.0)
		if decision == "EXCEPTION":
			return PolicyResult(
				decision=PolicyDecision.EXCEPTION,
				policy_reasons=["AI identified an exception"] + list(ai_decision.get("reason_codes", [])),
				blocked_conditions=["ai_exception"],
			)
		selected_id = ai_decision.get("selected_bank_transaction_id")
		if decision == "MATCH" and candidate_ids is not None and selected_id not in candidate_ids:
			return PolicyResult(
				decision=PolicyDecision.HUMAN_REVIEW,
				policy_reasons=["AI selected a bank candidate not supplied to the model"],
				blocked_conditions=["ai_selected_unknown_candidate"],
			)
		if (
			decision == "MATCH"
			and deterministic_score is not None
			and deterministic_score >= self.thresholds.auto_match_score

		):
			return PolicyResult(
				decision=PolicyDecision.AUTO_MATCH,
				policy_reasons=["Validated AI recommendation meets the automatic-match threshold"],
				blocked_conditions=[],
			)
		return PolicyResult(
			decision=PolicyDecision.HUMAN_REVIEW,
			policy_reasons=["AI recommendation requires human review"],
			blocked_conditions=["ai_review_required"],
		)


def evaluate_policy(
	candidates: Iterable[CandidateInput],
	*,
	thresholds: PolicyThresholds | Mapping[str, Any] | None = None,
) -> list[PolicyResult]:
	"""Convenience wrapper for deterministic policy evaluation."""
	return PolicyEngine(thresholds=thresholds).evaluate(candidates)
