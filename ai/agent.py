"""Google GenAI reasoning for ambiguous reconciliation evidence."""

from __future__ import annotations

import json
import os
import socket
from typing import Any, Mapping, Protocol

from pydantic import ValidationError

from ai.schemas import AIReconciliationDecision
from ai.prompts import build_reconciliation_prompt


class _ModelClient(Protocol):
	"""Minimal protocol used to keep the GenAI client injectable in tests."""

	models: Any


class ReconciliationAgent:
	"""Ask Gemini to reason about ambiguous evidence without doing arithmetic."""

	def __init__(
		self,
		model: str = "gemini-2.5-flash",
		client: _ModelClient | None = None,
		api_key: str | None = None,
		timeout_ms: int = 30_000,
	) -> None:
		"""Configure the model, request timeout, and optional test client."""
		if timeout_ms <= 0:
			raise ValueError("timeout_ms must be positive")
		self.model = model
		self.api_key = api_key if api_key is not None else os.getenv("GEMINI_API_KEY")
		self._client = client
		self.timeout_ms = timeout_ms

	def reason(
		self,
		payment: Mapping[str, Any],
		settlement: Mapping[str, Any] | None,
		bank_candidates: list[Mapping[str, Any]],
		deterministic_evidence: Mapping[str, Any],
	) -> AIReconciliationDecision:
		"""Return a validated AI decision, retrying once after API/parse failures.

		The prompt explicitly forbids financial arithmetic. If credentials are
		missing, the service fails, or the response is malformed, a conservative
		``REVIEW`` or ``EXCEPTION`` result is returned instead of dropping the case.
		"""
		if not payment.get("payment_id"):
			return self._fallback("EXCEPTION", "missing_payment_id", "Payment record has no payment ID")
		if settlement is None or not bank_candidates:
			return self._fallback(
				"EXCEPTION",
				"missing_source_evidence",
				"Required settlement or bank evidence is missing",
			)
		if not self.api_key and self._client is None:
			return self._fallback(
				"REVIEW", "ai_unavailable", "AI review is unavailable; human review is required"
			)

		last_error = "ai_api_error"
		for _attempt in range(2):
			try:
				response = self._generate(build_reconciliation_prompt(
					payment, settlement, bank_candidates, deterministic_evidence
				))
				return self._parse_response(response)
			except Exception as error:  # Keep one bad model call isolated to its record.
				last_error = self._classify_failure(error)
		return self._fallback(
			"REVIEW", last_error, "AI could not produce a valid decision; human review is required"
		)

	def _generate(self, prompt: str) -> Any:
		"""Generate structured content through the Google GenAI SDK."""
		if self._client is None:
			from google import genai
			from google.genai import types

			self._client = genai.Client(
				api_key=self.api_key,
				http_options=types.HttpOptions(timeout=self.timeout_ms),
			)
		return self._client.models.generate_content(
			model=self.model,
			contents=prompt,
			config={
				"response_mime_type": "application/json",
				"response_schema": AIReconciliationDecision,
			},
		)

	@staticmethod
	def _classify_failure(error: Exception) -> str:
		"""Map SDK, transport, and response failures to stable reason codes."""
		if isinstance(error, (TimeoutError, socket.timeout)) or "timeout" in type(error).__name__.lower():
			return "ai_timeout"
		if isinstance(error, (ValidationError, json.JSONDecodeError, TypeError, ValueError)):
			return "ai_validation_error"
		return "ai_api_error"

	@staticmethod
	def _parse_response(response: Any) -> AIReconciliationDecision:
		"""Extract and validate either SDK-parsed or JSON-text model output."""
		parsed = getattr(response, "parsed", None)
		if parsed is not None:
			return AIReconciliationDecision.model_validate(parsed)
		text = getattr(response, "text", response)
		if not isinstance(text, str):
			raise ValueError("model response has no text or parsed payload")
		return AIReconciliationDecision.model_validate(json.loads(text))

	@staticmethod
	def _fallback(decision: str, reason: str, explanation: str) -> AIReconciliationDecision:
		"""Create a conservative validated response for unavailable or bad AI."""
		return AIReconciliationDecision(
			decision=decision,
			confidence=0.0,
			reason_codes=[reason],
			explanation=explanation,
			missing_evidence=[] if decision == "REVIEW" else [reason],
		)


def reason_about_ambiguity(
	payment: Mapping[str, Any],
	settlement: Mapping[str, Any] | None,
	bank_candidates: list[Mapping[str, Any]],
	deterministic_evidence: Mapping[str, Any],
	*,
	model: str = "gemini-2.5-flash",
	client: _ModelClient | None = None,
	timeout_ms: int = 30_000,
) -> AIReconciliationDecision:
	"""Convenience wrapper around :class:`ReconciliationAgent`."""
	return ReconciliationAgent(model=model, client=client, timeout_ms=timeout_ms).reason(
		payment, settlement, bank_candidates, deterministic_evidence
	)
