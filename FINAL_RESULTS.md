# LedgerPilot — Final Evaluation Results

## Product

**LedgerPilot — AI Finance Controller**

> Models interpret. Rules authorize.

LedgerPilot reconciles payments, settlements, and bank transactions using deterministic matching and policy controls, with AI invoked only for ambiguous cases.

## Final Benchmark

| Metric | Result |
|---|---:|
| Total records | 100 |
| Matched | 66 |
| Match rate | 66.00% |
| AI-assisted | 10 |
| Human review | 26 |
| Exceptions | 8 |
| Precision | 98.48% |
| Recall | 92.86% |
| False auto-match | 1.52% |
| Automated tests | 37 passed |

## AI Layer

Provider: **Groq**

Model: **openai/gpt-oss-120b**

The AI agent is invoked for ambiguous reconciliation cases and produces a structured decision containing:

- decision
- confidence
- selected bank transaction
- reason codes
- explanation
- missing evidence

AI recommendations are validated by deterministic candidate and policy controls before becoming final decisions.

## Safety

AI does not directly authorize financial reconciliation outcomes.

The system preserves deterministic policy controls, candidate validation, exception handling, and auditability.

When AI is unavailable or produces an invalid response, the affected case is conservatively routed for review rather than being automatically matched.

## Verification

- Live Groq smoke test: passed
- Dashboard controller test: passed
- Reconciliation evaluation: passed
- Full pytest suite: 37/37 passed
- Streamlit dashboard: operational


