import json
from types import SimpleNamespace

import pytest

from ai.agent import ReconciliationAgent
from ai.prompts import RECONCILIATION_PROMPT_V1, build_reconciliation_prompt
from ai.schemas import AIReconciliationDecision
from engine.policy import PolicyDecision, PolicyEngine
from engine.reconciler import ReconciliationEngine


def candidate(**overrides):
    value = {
        "payment_id": "PAY-1",
        "settlement_id": "SET-1",
        "bank_transaction_id": "BANK-1",
        "match_score": 0.90,
        "overall_score": 0.90,
        "amount_score": 1.0,
    }
    value.update(overrides)
    return value


def ai_decision(decision="MATCH", confidence=0.99, selected="BANK-1"):
    return {
        "decision": decision,
        "confidence": confidence,
        "reason_codes": ["evidence_reviewed"],
        "explanation": "The supplied evidence was reviewed.",
        "missing_evidence": [],
        "selected_bank_transaction_id": selected,
    }


def test_ai_match_below_deterministic_threshold_cannot_auto_match():
    result = PolicyEngine().finalize_ai(
        PolicyEngine().evaluate_one(candidate()),
        ai_decision(),
        deterministic_score=0.90,
        candidate_ids={"BANK-1"},
    )

    assert result.decision is PolicyDecision.HUMAN_REVIEW


@pytest.mark.parametrize("blocked", [
    "missing_source_record",
    "multiple_viable_candidates",
    "duplicate_candidate",
    "amount_variance_above_tolerance",
])
def test_deterministic_blockers_prevent_auto_match(blocked):
    result = PolicyEngine().finalize_ai(
        PolicyEngine().evaluate_one(candidate()),
        ai_decision(),
        deterministic_score=0.99,
        candidate_ids={"BANK-1"},
    )
    blocked_result = result.model_copy(update={"blocked_conditions": [blocked]})

    final = PolicyEngine().finalize_ai(
        blocked_result, ai_decision(), deterministic_score=0.99, candidate_ids={"BANK-1"}
    )

    assert final.decision is not PolicyDecision.AUTO_MATCH


def test_ai_exception_becomes_exception():
    result = PolicyEngine().finalize_ai(
        PolicyEngine().evaluate_one(candidate()),
        ai_decision("EXCEPTION"),
        deterministic_score=0.99,
        candidate_ids={"BANK-1"},
    )

    assert result.decision is PolicyDecision.EXCEPTION


def test_ai_review_becomes_human_review():
    result = PolicyEngine().finalize_ai(
        PolicyEngine().evaluate_one(candidate()),
        ai_decision("REVIEW"),
        deterministic_score=0.99,
        candidate_ids={"BANK-1"},
    )

    assert result.decision is PolicyDecision.HUMAN_REVIEW


def test_legitimate_auto_match_remains_auto_match():
    result = PolicyEngine().finalize_ai(
        PolicyEngine().evaluate_one(candidate(match_score=0.99, overall_score=0.99)),
        ai_decision(),
        deterministic_score=0.99,
        candidate_ids={"BANK-1"},
    )

    assert result.decision is PolicyDecision.AUTO_MATCH


def test_unknown_ai_selected_candidate_requires_human_review():
    result = PolicyEngine().finalize_ai(
        PolicyEngine().evaluate_one(candidate()),
        ai_decision(selected="BANK-UNKNOWN"),
        deterministic_score=0.99,
        candidate_ids={"BANK-1"},
    )

    assert result.decision is PolicyDecision.HUMAN_REVIEW
    assert result.blocked_conditions == ["ai_selected_unknown_candidate"]


def test_ai_selected_candidate_is_not_replaced_by_deterministic_best():
    result = PolicyEngine().finalize_ai(
        PolicyEngine().evaluate_one(candidate(bank_transaction_id="BANK-1")),
        ai_decision(selected="BANK-2"),
        deterministic_score=0.90,
        candidate_ids={"BANK-1", "BANK-2"},
    )

    assert result.decision is PolicyDecision.HUMAN_REVIEW
    assert "ai_review_required" in result.blocked_conditions


def test_match_schema_requires_selected_candidate():
    with pytest.raises(ValueError, match="selected_bank_transaction_id"):
        AIReconciliationDecision(**ai_decision(selected=None))

    assert AIReconciliationDecision(**ai_decision("REVIEW", selected=None)).selected_bank_transaction_id is None


def test_prompt_is_versioned_and_contains_safety_instructions():
    prompt = build_reconciliation_prompt({"payment_id": "PAY-1"}, {}, [{"bank_transaction_id": "BANK-1"}], {})

    assert RECONCILIATION_PROMPT_V1 in prompt
    assert "never invent missing information" in prompt.lower()
    assert "selected_bank_transaction_id" in prompt
    assert '"bank_candidates"' in prompt


def test_agent_retry_and_structured_selected_candidate():
    payload = ai_decision()
    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=lambda **kwargs: SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))]
                )
            )
        )
    )
    result = ReconciliationAgent(client=client, api_key="test").reason(
        {"payment_id": "PAY-1"}, {"settlement_id": "SET-1"}, [{"bank_transaction_id": "BANK-1"}], {}
    )

    assert result.selected_bank_transaction_id == "BANK-1"


def _agent_inputs():
    return (
        {"payment_id": "PAY-1"},
        {"settlement_id": "SET-1"},
        [{"bank_transaction_id": "BANK-1"}],
        {},
    )


def test_missing_api_key_returns_ai_unavailable(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    result = ReconciliationAgent(api_key=None).reason(*_agent_inputs())

    assert result.decision == "REVIEW"
    assert result.reason_codes == ["ai_unavailable"]
    assert result.confidence == 0.0
    assert result.selected_bank_transaction_id is None


def test_timeout_returns_ai_timeout():
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
        create=lambda **kwargs: (_ for _ in ()).throw(TimeoutError("timed out"))
    )))

    result = ReconciliationAgent(client=client, api_key="test").reason(*_agent_inputs())

    assert result.reason_codes == ["ai_timeout"]


def test_api_failure_returns_ai_api_error():
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
        create=lambda **kwargs: (_ for _ in ()).throw(ConnectionError("offline"))
    )))

    result = ReconciliationAgent(client=client, api_key="test").reason(*_agent_inputs())

    assert result.reason_codes == ["ai_api_error"]


def test_invalid_structured_response_returns_validation_error():
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
        create=lambda **kwargs: SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="not json"))]
        )
    )))

    result = ReconciliationAgent(client=client, api_key="test").reason(*_agent_inputs())

    assert result.reason_codes == ["ai_validation_error"]


def test_successful_retry_after_first_api_failure():
    payload = ai_decision()
    calls = {"count": 0}

    def generate(**kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise ConnectionError("temporary failure")
        return SimpleNamespace(text=json.dumps(payload))

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=generate)))
    result = ReconciliationAgent(client=client, api_key="test").reason(*_agent_inputs())

    assert calls["count"] == 2
    assert result.decision == "MATCH"


def test_both_attempts_fail_with_safe_review():
    calls = {"count": 0}

    def generate(**kwargs):
        calls["count"] += 1
        raise ConnectionError("offline")

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=generate)))
    result = ReconciliationAgent(client=client, api_key="test").reason(*_agent_inputs())

    assert calls["count"] == 2
    assert result.decision == "REVIEW"
    assert result.confidence == 0.0
    assert result.reason_codes == ["ai_api_error"]
    assert result.selected_bank_transaction_id is None


def test_ai_audit_contains_complete_decision():
    class FakeAgent:
        model = "test-model"

        def reason(self, payment, settlement, bank_candidates, deterministic_evidence):
            return AIReconciliationDecision(**ai_decision("MATCH", 0.99, "BANK-1"))

    output = ReconciliationEngine(ai_agent=FakeAgent()).reconcile(
        [{"payment_id": "PAY-1", "transaction_reference": "REF-1", "merchant_name": "Merchant", "payment_date": "2026-09-04"}],
        [{"payment_id": "PAY-1", "settlement_id": "SET-1", "settlement_date": "2026-09-04", "net_amount": "100.00"}],
        [{"bank_transaction_id": "BANK-1", "transaction_reference": "REF 1", "merchant_name": "Merchant", "transaction_date": "2026-09-05", "amount": "100.00"}],
    )
    event = output.audit_events[0]

    assert event.ai_used is True
    assert event.ai_model == "test-model"
    assert event.ai_decision == "MATCH"
    assert event.ai_confidence == 0.99
    assert event.ai_selected_bank_transaction_id == "BANK-1"
    assert event.ai_reason_codes == ["evidence_reviewed"]
    assert event.ai_explanation
    assert event.final_policy_decision in {"AUTO_MATCH", "HUMAN_REVIEW"}


def test_reconciler_rejects_unknown_ai_selected_candidate():
    class FakeAgent:
        model = "test-model"

        def reason(self, payment, settlement, bank_candidates, deterministic_evidence):
            return AIReconciliationDecision(**ai_decision(selected="BANK-DOES-NOT-EXIST"))

    output = ReconciliationEngine(ai_agent=FakeAgent()).reconcile(
        [{"payment_id": "PAY-1", "transaction_reference": "REF-1", "merchant_name": "Merchant", "payment_date": "2026-09-04"}],
        [{"payment_id": "PAY-1", "settlement_id": "SET-1", "settlement_date": "2026-09-04", "net_amount": "100.00"}],
        [{"bank_transaction_id": "BANK-1", "transaction_reference": "REF 1", "merchant_name": "Merchant", "transaction_date": "2026-09-05", "amount": "100.00"}],
    )

    assert output.human_review_cases[0]["decision"] == "HUMAN_REVIEW"
    assert "ai_selected_unknown_candidate" in output.human_review_cases[0]["blocked_conditions"]
