"""Versioned prompts for evidence-only reconciliation reasoning."""

from __future__ import annotations

import json
from typing import Any, Mapping


RECONCILIATION_PROMPT_V1 = "RECONCILIATION_PROMPT_V1"


def build_reconciliation_prompt(
	payment: Mapping[str, Any],
	settlement: Mapping[str, Any],
	bank_candidates: list[Mapping[str, Any]],
	deterministic_evidence: Mapping[str, Any],
) -> str:
	"""Build a structured, evidence-only prompt for reconciliation review."""
	payload = {
		"payment": dict(payment),
		"settlement": dict(settlement),
		"bank_candidates": [dict(candidate) for candidate in bank_candidates],
		"deterministic_evidence": dict(deterministic_evidence),
	}
	return (
		f"Prompt version: {RECONCILIATION_PROMPT_V1}. "
		"Compare only the supplied payment, settlement, bank candidates, and "
		"deterministic evidence. Never invent missing information. Do not calculate "
		"financial totals or perform financial authorization. Return structured output "
		"matching AIReconciliationDecision. Choose exactly one supplied "
		"bank_transaction_id when decision=MATCH; selected_bank_transaction_id must "
		"come from the supplied candidates. Use REVIEW when evidence is ambiguous. "
		"Use EXCEPTION when required evidence is missing or inconsistent.\n\n"
		+ json.dumps(payload, default=str, sort_keys=True)
	)
