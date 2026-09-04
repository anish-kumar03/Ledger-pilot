"""Streamlit dashboard for the LedgerPilot reconciliation controller."""

from __future__ import annotations

import json
import os
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from engine.reconciler import ReconciliationEngine, ReconciliationOutput
from evaluation.evaluator import (
	BANK_TRANSACTIONS_PATH,
	GROUND_TRUTH_PATH,
	PAYMENTS_PATH,
	SETTLEMENTS_PATH,
	compare_with_ground_truth,
	load_ground_truth,
	normalize_reconciliation_output,
)
from evaluation.metrics import calculate_all_metrics


ROOT = Path(__file__).resolve().parent


def _init_state() -> None:
	"""Initialize dashboard state without running the pipeline on import."""
	defaults = {
		"reconciliation_output": None,
		"evaluation_records": [],
		"metrics": {},
		"last_run_at": None,
		"processing_seconds": None,
		"run_error": None,
		"controller_answer": None,
	}
	for key, value in defaults.items():
		st.session_state.setdefault(key, value)


def _run_reconciliation() -> None:
	"""Run the existing engine and evaluation layer, storing one current run."""
	started = time.perf_counter()
	try:
		output = ReconciliationEngine().reconcile(
			PAYMENTS_PATH, SETTLEMENTS_PATH, BANK_TRANSACTIONS_PATH
		)
		records = normalize_reconciliation_output(output)
		evaluated = compare_with_ground_truth(records, load_ground_truth(GROUND_TRUTH_PATH))
		st.session_state["reconciliation_output"] = output
		st.session_state["evaluation_records"] = evaluated
		st.session_state["metrics"] = calculate_all_metrics(evaluated)
		st.session_state["last_run_at"] = datetime.now(timezone.utc)
		st.session_state["run_error"] = None
		st.session_state["controller_answer"] = None
	except Exception as error:
		st.session_state["run_error"] = f"Reconciliation failed: {error}"
	finally:
		st.session_state["processing_seconds"] = time.perf_counter() - started


def _ai_status(output: ReconciliationOutput | None) -> tuple[str, str]:
	"""Derive AI availability from the current run's audit events."""
	if output is None:
		return "Not run", "Run reconciliation to check the controller"
	if any(
		event.ai_used and any(code.startswith("ai_") for code in event.ai_reason_codes)
		for event in output.audit_events
	):
		return "Degraded", "AI failed safely; affected cases remained in review"
	if any(event.ai_used for event in output.audit_events):
		return "Available", "AI-assisted cases were routed through final policy"
	return "Available", "No ambiguous cases required AI in this run"


def render_header() -> None:
	"""Render the dashboard masthead and run controls."""
	st.markdown(
		"<div class='masthead'><div class='brand'>LedgerPilot</div>"
		"<div class='subtitle'>AI Finance Controller</div></div>",
		unsafe_allow_html=True,
	)
	left, right = st.columns([4, 1])
	with left:
		st.markdown("Reconcile payments, settlements and bank transactions with deterministic controls and AI-assisted exception analysis.")
	with right:
		if st.button("Run Reconciliation", type="primary", use_container_width=True):
			with st.spinner("Processing payments, settlements, and bank transactions"):
				_run_reconciliation()
			st.rerun()


def _metric_value(metrics: dict[str, Any], key: str, percent: bool = False) -> str:
	"""Format an injected runtime metric for display."""
	value = metrics.get(key, 0)
	return f"{value:.2%}" if percent else f"{value:,}"


def render_kpis(metrics: dict[str, Any]) -> None:
	"""Render KPI cards from runtime metrics only."""
	items = [
		("Records Processed", _metric_value(metrics, "total_records"), "current run"),
		("Match Rate", _metric_value(metrics, "match_rate", True), "auto-matched"),
		("Precision", _metric_value(metrics, "precision", True), "ground-truth accuracy"),
		("Recall", _metric_value(metrics, "recall", True), "matched coverage"),
		("AI Assisted", _metric_value(metrics, "ai_assisted"), "review handoffs"),
		("Exceptions", _metric_value(metrics, "exceptions"), "requires attention"),
	]
	columns = st.columns(6)
	for column, (label, value, detail) in zip(columns, items):
		with column:
			st.markdown(
				f"<div class='kpi'><div class='kpi-label'>{label}</div>"
				f"<div class='kpi-value'>{value}</div><div class='kpi-detail'>{detail}</div></div>",
				unsafe_allow_html=True,
			)


def render_status(output: ReconciliationOutput | None, metrics: dict[str, Any]) -> None:
	"""Render concise operational status from current runtime state."""
	ai_label, ai_detail = _ai_status(output)
	items = [
		("Reconciliation engine", "Operational", "Deterministic pipeline ready"),
		("Evaluation engine", "Operational" if metrics else "Ready", "Ground-truth metrics available" if metrics else "Awaiting a run"),
		("AI controller", ai_label, ai_detail),
	]
	st.markdown("**System status**")
	columns = st.columns(3)
	for column, (label, value, detail) in zip(columns, items):
		with column:
			state_class = "status-good" if value == "Operational" or value == "Available" else "status-muted"
			st.markdown(
				f"<div class='status'><span class='{state_class}'></span><div><b>{label}</b>"
				f"<br><strong>{value}</strong><small>{detail}</small></div></div>",
				unsafe_allow_html=True,
			)


def render_charts(records: list[dict[str, Any]]) -> None:
	"""Render compact decision and reason-code charts from runtime records."""
	if not records:
		return
	decisions = pd.Series(
		{decision: sum(record.get("decision") == decision for record in records)
		 for decision in ("AUTO_MATCH", "HUMAN_REVIEW", "EXCEPTION")}
	).to_frame("Records")
	reasons = Counter(
		code for record in records
		if record.get("decision") in {"HUMAN_REVIEW", "EXCEPTION"}
		for code in record.get("reason_codes", [])
	)
	left, right = st.columns(2)
	with left:
		st.markdown("**Decision distribution**")
		st.bar_chart(decisions, height=190, color="#0b6e69")
	with right:
		st.markdown("**Top exception and review reasons**")
		reason_frame = pd.DataFrame(reasons.most_common(8), columns=["Reason code", "Records"]).set_index("Reason code")
		if reason_frame.empty:
			st.caption("No exception or review reasons in the current run.")
		else:
			st.bar_chart(reason_frame, height=190, color="#b36b00")


def _records_frame(records: list[dict[str, Any]]) -> pd.DataFrame:
	"""Build the compact table view from normalized engine records."""
	rows = []
	for record in records:
		evidence = record.get("evidence") or []
		best = evidence[0] if evidence and isinstance(evidence[0], dict) else {}
		rows.append(
			{
				"Payment ID": record.get("payment_id"),
				"Settlement ID": record.get("settlement_id") or best.get("settlement_id"),
				"Bank Transaction ID": record.get("bank_transaction_id") or best.get("bank_transaction_id"),
				"Decision": record.get("decision"),
				"Score": best.get("overall_score", best.get("match_score", 0.0)),
				"AI Used": bool(record.get("ai_assisted")),
				"Reason": "; ".join(record.get("reason_codes", [])),
				"_record": record,
			}
		)
	return pd.DataFrame(rows)


def render_results(records: list[dict[str, Any]]) -> None:
	"""Render a filterable reconciliation results table."""
	st.subheader("Reconciliation Results")
	if not records:
		st.info("Run reconciliation to populate results.")
		return
	left, middle, right = st.columns([2, 2, 3])
	with left:
		decisions = st.multiselect(
			"Decision", ["AUTO_MATCH", "HUMAN_REVIEW", "EXCEPTION"], default=[]
		)
	with middle:
		ai_filter = st.selectbox("AI assisted", ["All", "Yes", "No"])
	with right:
		search = st.text_input("Search payment ID", placeholder="PAY-0009")
	frame = _records_frame(records)
	if decisions:
		frame = frame[frame["Decision"].isin(decisions)]
	if ai_filter != "All":
		frame = frame[frame["AI Used"] == (ai_filter == "Yes")]
	if search:
		frame = frame[frame["Payment ID"].str.contains(search, case=False, na=False)]
	display = frame.drop(columns=["_record"], errors="ignore").copy()
	if not display.empty:
		display["Score"] = display["Score"].map(lambda value: f"{float(value):.2f}")
	st.dataframe(display, hide_index=True, use_container_width=True, height=420)


def _detail_from_record(record: dict[str, Any]) -> dict[str, Any]:
	"""Extract deterministic and AI investigation fields from a result record."""
	evidence = record.get("evidence") or []
	best = evidence[0] if evidence and isinstance(evidence[0], dict) else {}
	ai = record.get("ai_decision", {})
	settlement = {
		key: value
		for key, value in record.items()
		if key == "settlement_id" or key.startswith("settlement_")
	}
	if not settlement:
		settlement = {
			key: value
			for key, value in best.items()
			if key == "settlement_id" or key.startswith("settlement_")
		}
	return {
		"payment": {key: value for key, value in record.items() if key.startswith("normalized_") is False},
		"settlement": settlement,
		"selected bank candidate": record.get("bank_transaction_id") or best.get("bank_transaction_id"),
		"deterministic score": best.get("overall_score", best.get("match_score")),
		"signal scores": {key: best.get(key) for key in (
			"reference_score", "amount_score", "date_score", "merchant_score", "invoice_score"
		) if key in best},
		"matching signals": best.get("matching_signals", []),
		"policy reasons": record.get("policy_reasons", []),
		"blocked conditions": record.get("blocked_conditions", []),
		"ai": ai,
	}


def render_exceptions(
	records: list[dict[str, Any]], output: ReconciliationOutput | None = None
) -> None:
	"""Render an investigation panel for human review and exception records."""
	st.subheader("Exception Investigation")
	cases = [record for record in records if record.get("decision") in {"HUMAN_REVIEW", "EXCEPTION"}]
	if not cases:
		st.info("No human-review or exception records in the current run.")
		return
	by_id = {record.get("payment_id"): record for record in cases}
	selected_id = st.selectbox("Payment ID", list(by_id))
	record = by_id[selected_id]
	detail = _detail_from_record(record)
	audit_events = {
		str(event.payment_id): event
		for event in (output.audit_events if output is not None else [])
		if event.payment_id is not None
	}
	event = audit_events.get(str(selected_id))
	if event is not None and event.ai_used:
		detail["ai"] = {
			"decision": event.ai_decision,
			"confidence": event.ai_confidence,
			"selected_bank_transaction_id": event.ai_selected_bank_transaction_id,
			"reason_codes": event.ai_reason_codes,
			"explanation": event.ai_explanation,
			"missing_evidence": event.ai_missing_evidence,
			"model": event.ai_model,
		}
	left, right = st.columns(2)
	with left:
		st.markdown("### Transaction Evidence")
		st.json({
			"payment": detail.get("payment", {}),
			"settlement": detail.get("settlement") or {"status": "Unavailable"},
			"bank candidate": detail.get("selected bank candidate") or "Unavailable",
		})
		st.markdown("### Deterministic Analysis")
		st.json({key: detail.get(key) for key in ("deterministic score", "signal scores", "matching signals")})
	with right:
		st.markdown("### AI Analysis")
		if detail["ai"]:
			st.info(f"AI RECOMMENDATION: {detail['ai'].get('decision', 'Unavailable')}")
			st.json(detail["ai"])
		else:
			st.caption("AI was not used for this record.")
		st.markdown("### Final Decision")
		st.warning(f"FINAL POLICY DECISION: {record.get('decision')}")
		st.write({"policy reasons": detail["policy reasons"], "blocked conditions": detail["blocked conditions"]})
		st.markdown("### Why this decision?")
		st.write(_decision_explanation(record, detail))


def _decision_explanation(record: dict[str, Any], detail: dict[str, Any]) -> str:
	"""Create a concise deterministic explanation from recorded evidence only."""
	parts = []
	if detail["matching signals"]:
		parts.append("Matching signals: " + ", ".join(detail["matching signals"]))
	if detail["deterministic score"] is not None:
		parts.append(f"Deterministic score: {float(detail['deterministic score']):.2f}")
	if detail["blocked conditions"]:
		parts.append("Policy blockers: " + ", ".join(detail["blocked conditions"]))
	if not parts and detail["policy reasons"]:
		parts.extend(detail["policy reasons"])
	return ". ".join(parts) + "." if parts else "No additional evidence was recorded."


def render_audit(output: ReconciliationOutput | None) -> None:
	"""Render filterable audit events with expandable evidence."""
	st.subheader("Audit Trail")
	if output is None or not output.audit_events:
		st.info("Run reconciliation to populate the audit trail.")
		return
	events = [event.model_dump() for event in output.audit_events]
	left, middle, right = st.columns([2, 2, 3])
	with left:
		decision_filter = st.multiselect("Audit decision", ["AUTO_MATCH", "HUMAN_REVIEW", "EXCEPTION"], default=[])
	with middle:
		ai_filter = st.selectbox("Audit AI used", ["All", "Yes", "No"], key="audit_ai_filter")
	with right:
		payment_filter = st.text_input("Audit payment ID", key="audit_payment_filter")
	for event in events:
		if decision_filter and event["decision"] not in decision_filter:
			continue
		if ai_filter != "All" and event["ai_used"] != (ai_filter == "Yes"):
			continue
		if payment_filter and payment_filter.lower() not in str(event.get("payment_id", "")).lower():
			continue
		label = f"{event['event_id']} | {event.get('payment_id')} | {event['decision']}"
		with st.expander(label):
			st.dataframe(pd.DataFrame([{
				"Event ID": event["event_id"], "Timestamp": event["created_at"],
				"Payment ID": event.get("payment_id"), "Decision": event["decision"],
				"AI Used": event["ai_used"], "AI Model": event.get("ai_model"),
				"AI Decision": event.get("ai_decision"), "AI Confidence": event.get("ai_confidence"),
				"Selected Bank Candidate": event.get("ai_selected_bank_transaction_id"),
				"Reason Codes": "; ".join(event.get("reason_codes", [])),
				"Final Policy Decision": event.get("final_policy_decision"),
			}]), hide_index=True, use_container_width=True)
			st.json(event.get("evidence", {}))


def _controller_context(records: list[dict[str, Any]], metrics: dict[str, Any]) -> dict[str, Any]:
	"""Build bounded structured context from the current run only."""
	return {
		"metrics": metrics,
		"top_exception_reasons": Counter(
			code for record in records if record.get("decision") == "EXCEPTION" for code in record.get("reason_codes", [])
		).most_common(10),
		"records": records,
	}


def _ask_gemini(question: str, context: dict[str, Any]) -> str:
	"""Ask Gemini a read-only current-run question without creating another agent."""
	if not os.getenv("GEMINI_API_KEY"):
		return "Insufficient evidence in the current reconciliation run. Gemini is unavailable."
	try:
		from google import genai
		from google.genai import types

		client = genai.Client(
			api_key=os.environ["GEMINI_API_KEY"],
			http_options=types.HttpOptions(timeout=30_000),
		)
		prompt = (
			"You are a read-only finance controller answering questions about the supplied current "
			"reconciliation run. Use only the JSON context. Do not modify records, decisions, policy, "
			"or create financial records. Never invent missing data. If the answer is unavailable, say "
			"exactly: Insufficient evidence in the current reconciliation run.\n\n"
			f"Question: {question}\nContext: {json.dumps(context, default=str, sort_keys=True)}"
		)
		response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
		answer = getattr(response, "text", None)
		return answer.strip() if isinstance(answer, str) and answer.strip() else "Insufficient evidence in the current reconciliation run."
	except Exception:
		return "Insufficient evidence in the current reconciliation run."


def render_controller(records: list[dict[str, Any]], metrics: dict[str, Any]) -> None:
	"""Render the read-only Ask LedgerPilot controller panel."""
	st.subheader("Ask LedgerPilot")
	st.caption("Read-only answers grounded in the current reconciliation run")
	question = st.text_input("Question", placeholder="Why is PAY-0009 unresolved?")
	if st.button("Ask Controller", disabled=not records):
		with st.spinner("Reviewing current-run evidence"):
			st.session_state["controller_answer"] = _ask_gemini(
				question, _controller_context(records, metrics)
			)
	if st.session_state.get("controller_answer"):
		st.markdown(st.session_state["controller_answer"])


def main() -> None:
	"""Render the LedgerPilot dashboard."""
	st.set_page_config(page_title="LedgerPilot — AI Finance Controller", page_icon="L", layout="wide")
	st.markdown(
		"""
		<style>
		:root { --ink:#17202a; --muted:#64707d; --line:#dfe5ea; --paper:#f6f8fa; --accent:#0b6e69; --warn:#b36b00; }
		.stApp { background:var(--paper); color:var(--ink); }
		.block-container { max-width:1400px; padding-top:2rem; }
		.masthead { border-bottom:1px solid var(--line); padding:0 0 1rem; margin-bottom:1.4rem; }
		.brand { color:var(--accent); font-size:1.65rem; font-weight:800; letter-spacing:.12em; }
		.subtitle { color:var(--muted); font-size:1rem; margin-top:.2rem; }
		.kpi { background:white; border:1px solid var(--line); border-radius:8px; border-top:3px solid var(--accent); padding:1rem; min-height:106px; box-shadow:0 1px 2px rgba(23,32,42,.04); }
		.kpi-label { color:var(--muted); font-size:.78rem; text-transform:uppercase; letter-spacing:.05em; }
		.kpi-value { color:var(--ink); font-size:1.7rem; font-weight:750; margin-top:.35rem; }
		.kpi-detail { color:var(--muted); font-size:.75rem; margin-top:.25rem; }
		.status { background:white; border:1px solid var(--line); border-radius:8px; padding:.75rem 1rem; display:flex; gap:.7rem; align-items:flex-start; }
		.status strong { display:block; margin-top:.2rem; }
		.status small { color:var(--muted); display:block; margin-top:.25rem; }
		.status-good, .status-muted { width:9px; height:9px; border-radius:50%; display:inline-block; margin-top:.35rem; background:#16836e; }
		.status-muted { background:#b36b00; }
		h1, h2, h3 { color:var(--ink); }
		section[data-testid="stSidebar"] { background:#172b35; }
		section[data-testid="stSidebar"] * { color:#f4f7f8; }
		</style>
		""",
		unsafe_allow_html=True,
	)
	_init_state()
	with st.sidebar:
		st.markdown("## LEDGERPILOT")
		st.caption("AI Finance Controller")
		st.divider()
		st.markdown("**Reconciliation Run**")
		st.markdown("**Reconciliation Results**")
		st.markdown("**Exceptions**")
		st.markdown("**Audit Trail**")
		if st.session_state.get("last_run_at"):
			st.divider()
			st.caption(f"Last run: {st.session_state['last_run_at'].astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}")
			st.caption(f"Duration: {st.session_state.get('processing_seconds', 0):.2f}s")
	render_header()
	if st.session_state.get("run_error"):
		st.error(st.session_state["run_error"])
	metrics = st.session_state.get("metrics", {})
	output = st.session_state.get("reconciliation_output")
	render_status(output, metrics)
	st.divider()
	render_kpis(metrics)
	st.divider()
	records = st.session_state.get("evaluation_records", [])
	render_charts(records)
	st.divider()
	render_results(records)
	st.divider()
	render_exceptions(records, output)
	st.divider()
	render_audit(output)
	st.divider()
	render_controller(records, metrics)


if __name__ == "__main__":
	main()
