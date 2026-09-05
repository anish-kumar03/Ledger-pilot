# LedgerPilot — AI Finance Controller

**Live Application:** https://ledgerpilot.streamlit.app/



## 1. Executive Overview

**LedgerPilot** is a web-based AI Finance Controller that reconciles payments, settlements, and bank transactions by combining deterministic controls with AI-assisted exception analysis.

**Problem:** Financial reconciliation is highly manual, error-prone, and expensive. Transactions are rarely 1:1 identical across payment gateways, merchant records, and bank statements. Simple automated rules fail on ambiguous cases, while fully autonomous AI agents are unsafe for authorizing financial movements.

**Value Proposition:** LedgerPilot bridges the gap between rigid rules and unsafe automation. It uses a deterministic engine to resolve clear matches and safely routes ambiguous cases to an embedded AI Reconciliation Agent.

**Target Users:** Finance operations analysts, reconciliation analysts, and payment operations teams.

**Technical Approach:** A deterministic-first pipeline (normalization → candidate generation → scoring → policy) handles the bulk of the workload. An AI agent reasons over edge cases (missing references, merchant name mismatches) to provide structured recommendations. Crucially, the AI does not have the final say.

**Core Safety Philosophy:** *Models interpret. Rules authorize.* The AI agent acts as a highly capable analyst reviewing evidence, but the deterministic Policy Engine always has the final authority to accept the recommendation, block it, or flag it for human review.

---

## 2. Razorpay Hackathon — Track 04: AI Finance Controller

This project was built for the **Razorpay Hackathon (Track 04)**. We selected this problem because financial reconciliation is a massive operational bottleneck where AI can provide immediate value—provided it is deployed safely.

LedgerPilot maps directly to Track 04 by acting as an AI Finance Controller that closes the finance-ops loop. It participates in the workflow by reasoning through ambiguous data, providing clear audit trails, and gracefully escalating unresolved cases to human operators. The built-in evaluation framework proves its measurable performance against a ground-truth dataset.

### Requirement to Implementation Mapping

| Track Requirement | LedgerPilot Implementation | Evidence / Mechanism | Why It Matters |
|---|---|---|---|
| AI-Powered Reconciliation | `ai/agent.py` | Uses `openai/gpt-oss-120b` via Groq for ambiguous cases | Resolves mismatches rules cannot handle. |
| Operational Interface | `app.py` | Streamlit dashboard with KPIs, charts, and detailed exception review | Provides a functional finance-ops workspace. |
| Measurable Accuracy | `evaluation/evaluator.py` | Compares engine output against `ground_truth.csv` | Proves the solution works objectively (98.48% Precision). |
| Safety & Control | `engine/policy.py` | Policy Engine finalizes all AI recommendations | Prevents LLM hallucinations from approving transactions. |
| Auditability | `AuditEvent` schema | Complete deterministic and AI evidence saved per payment | Financial compliance requires explainable decisions. |

---

## 3. Problem Statement

**Transaction reconciliation** is the process of ensuring that internal payment records match gateway settlements and final bank account deposits.

Because a single business transaction traverses multiple systems, it rarely looks identical at each step:
- **Reference differences:** `TRX-998` vs `REF 998`
- **Merchant-name differences:** `Acme Corp` vs `Acme.com Inc`
- **Date differences:** Timezone shifts or processing delays (e.g., T+2 settlement)
- **Amount differences:** Deducted processing fees or batching
- **Missing fields:** Truncated bank descriptions
- **Duplicate candidates:** Multiple transactions with the same amount on the same day

**The Operator Perspective:** Manual reconciliation is incredibly tedious and expensive. Analysts spend hours hunting for matching bank records, delaying financial closing. Exceptions are operationally important because they often represent delayed settlements, system failures, or missing funds.

**The System Perspective:** Incorrect automatic matches (false positives) are dangerous, leading to accounting errors or lost revenue. Simple exact-matching algorithms leave too many exceptions for humans. However, blindly trusting a Large Language Model (LLM) is also unsafe because models can hallucinate candidates, ignore strict variance rules, or confidently authorize invalid matches.

---

## 4. Solution Overview

LedgerPilot solves this by embedding an AI agent *inside* a deterministic workflow. 

```text
                        ┌──────────────────────────────┐
                        │        Data Sources          │
                        │ (Payments, Settlements, Bank)│
                        └──────────────┬───────────────┘
                                       │
                        ┌──────────────▼───────────────┐
                        │     Normalization Engine     │ (Deterministic)
                        └──────────────┬───────────────┘
                                       │
                        ┌──────────────▼───────────────┐
                        │     Matching Engine          │ (Deterministic)
                        │    (Candidate Generation)    │
                        └──────────────┬───────────────┘
                                       │
                        ┌──────────────▼───────────────┐
                        │     Scoring Engine           │ (Deterministic)
                        └──────────────┬───────────────┘
                                       │
                        ┌──────────────▼───────────────┐
                        │     Policy Engine            │ (Deterministic)
                        └──────────────┬───────────────┘
                                       │
               ┌───────────────────────┴───────────────────────┐
               │                                               │
    ┌──────────▼──────────┐                         ┌──────────▼──────────┐
    │   Clear Match       │                         │   Ambiguous Case    │
    │  (Score >= 0.95)    │                         │(Score >= 0.85 & < 0.95)
    └──────────┬──────────┘                         └──────────┬──────────┘
               │                                               │
               │                                    ┌──────────▼──────────┐
               │                                    │ AI Reconciliation   │ (AI-Powered)
               │                                    │ Agent (Groq)        │
               │                                    └──────────┬──────────┘
               │                                               │
               │                                    ┌──────────▼──────────┐
               │                                    │ Candidate Validation│ (Deterministic)
               │                                    └──────────┬──────────┘
               │                                               │
               │                                    ┌──────────▼──────────┐
               │                                    │ Policy Validation   │ (Deterministic)
               │                                    └──────────┬──────────┘
               │                                               │
               └───────────────────────┬───────────────────────┘
                                       │
                        ┌──────────────▼───────────────┐
                        │        Final Outcome         │ (AUTO_MATCH, HUMAN_REVIEW, EXCEPTION)
                        └──────────────┬───────────────┘
                                       │
                        ┌──────────────▼───────────────┐
                        │        Audit Trail           │
                        └──────────────┬───────────────┘
                                       │
               ┌───────────────────────┴───────────────────────┐
               │                                               │
    ┌──────────▼──────────┐                         ┌──────────▼──────────┐
    │  Evaluation Layer   │                         │  Dashboard (UI)     │
    └─────────────────────┘                         └─────────────────────┘
```

---

## 5. Is LedgerPilot a Web Application or an AI Agent?

LedgerPilot is **both**, but they are distinct conceptual components.

| Feature | Web Application (Streamlit) | AI Agent (ReconciliationAgent) |
|---|---|---|
| **Responsibility** | User-facing operational interface | Reasoning component inside the workflow |
| **Implementation** | `app.py` | `ai/agent.py` |
| **Inputs** | User clicks, filters, search queries | Ambiguous payment, settlement, bank records |
| **Outputs** | Visual charts, tables, exception UI | Structured JSON recommendation |
| **User Interaction** | Direct | None (Runs headless during processing) |
| **Reasoning** | None (Deterministic UI rendering) | Evaluates ambiguous financial evidence |
| **Control** | Driven by user actions | Driven by the deterministic Policy Engine |
| **Validation** | Pydantic and Streamlit forms | Strict fallback schemas and policy constraints |

### How a Traditional Web App Works
A user uploads a file, the backend runs an `if/else` script, and the results are rendered on the screen. Any edge case failing the strict `if/else` rules is thrown into an exception queue for a human to read.

### How the LedgerPilot AI Agent Works
LedgerPilot catches the edge cases that fail the strict `if/else` rules, formats the specific evidence, and asks the AI Agent to review the ambiguity (just like a junior analyst). The Agent produces a structured decision, which the system mathematically validates before showing the final result to the user.

An LLM call is just a string prediction. LedgerPilot is more than a chatbot because it operates as an **AI agent participating in a controlled workflow** with validation and fallback logic.

---

## 6. What Makes LedgerPilot Agentic?

LedgerPilot's `ReconciliationAgent` exhibits true agentic behavior within the scope of its workflow:
- **Context:** It receives highly specific, localized evidence (a payment, a settlement, and scoped bank candidates).
- **Ambiguity Reasoning:** It evaluates soft signals (e.g., matching "Netflix" to "NFLX SUB").
- **Structured Recommendation:** It does not chat; it outputs a strict Pydantic JSON schema containing decisions, confidence scores, and missing evidence flags.
- **Validation & Constraints:** It operates within strict constraints (it cannot select a candidate it wasn't given).
- **Fallback:** If the API times out or the response is malformed, it degrades safely to a `REVIEW` state rather than crashing.
- **Audit & Workflow Participation:** Its decisions are logged completely and are critical to closing the financial loop.

### What LedgerPilot is NOT
We are technically honest about the current implementation. LedgerPilot is **not**:
- A fully autonomous general-purpose agent.
- A multi-agent system.
- An unrestricted financial decision maker.
- A tool-using autonomous planner (no RAG, no web browsing, no function calling, no live SQL execution).

It is a **controlled AI reconciliation agent embedded in a deterministic workflow.**

---

## 7. End-to-End Technical Workflow

Let's follow one transaction through the system:

1. **Input:** `PAY-0051` enters the system.
2. **Normalization:** The engine strips symbols from the reference (`REF-99` becomes `REF99`) and cleans the merchant name.
3. **Candidate Generation:** The engine searches `bank_transactions.csv` for candidates within a 3-day window and similar amounts. It finds `BANK-0051`.
4. **Scoring:** The deterministic scorer evaluates the signals. Reference mismatches slightly, but the amount is exact. Score = `0.88`.
5. **Policy:** The policy engine sees `0.88`. This is below `auto_match` (0.95) but above `ai_review` (0.85). It routes to the AI.
6. **AI Reasoning:** The AI Agent is invoked. It analyzes the specific differences, realizes the mismatch is a known abbreviation, and recommends `MATCH` with 95% confidence for `BANK-0051`.
7. **Validation:** The system verifies that `BANK-0051` was actually an allowed candidate.
8. **Final Outcome:** The policy engine accepts the validated AI recommendation and marks the final decision as `AUTO_MATCH`.
9. **Audit:** A complete `AuditEvent` is saved containing the exact scores, the AI's reason codes, and the final policy decision.

---

## 8. Data Architecture

The project uses a structured CSV dataset representing different stages of the payment lifecycle.

- **`payments.csv`**: The internal source of truth (Payment ID, Date, Amount, Merchant, Reference).
- **`settlements.csv`**: Data from the payment gateway (Settlement ID, Payment ID, Net Amount, Fees).
- **`bank_transactions.csv`**: Data from the bank statement (Bank ID, Date, Amount, Description).
- **`ground_truth.csv`**: The answer key used by the evaluation layer to measure actual accuracy.

**Synthetic Data & Ambiguity:** The dataset contains 100 records. While most are straightforward, controlled ambiguous IDs `PAY-0051` through `PAY-0060` are intentionally engineered with complex ambiguities (missing references, extreme date shifts, typos) to trigger the AI agent. This controlled ambiguity is necessary for validating AI behavior reliably.

---

## 9. Normalization Engine

Implemented in `engine/normalizer.py`.

Normalization reduces superficial noise before scoring, significantly improving matching precision.
- **Dates:** Coerced to standard `YYYY-MM-DD` (e.g. `pd.to_datetime`).
- **Amounts:** Standardized to two-decimal `Decimal` objects, stripping currencies and interpreting parenthesis as negative.
- **References:** Spaces, slashes, and hyphens are removed; letters are uppercased (`INV/2023-A` → `INV2023A`).
- **Merchant Names:** Special characters removed, case folded, and whitespace stripped.

---

## 10. Matching Engine (Candidate Generation)

Implemented in `engine/matcher.py`.

The matcher does not make decisions; it generates plausible bank candidates for a payment to prevent the AI from having to search the entire database. It operates in stages:
1. **Exact Reference:** Raw strings match exactly.
2. **Normalized Reference:** Cleaned strings match.
3. **Amount/Date Logic:** Amounts match perfectly, and dates are within a configurable tolerance (default 3 days).
4. **Invoice/Merchant Similarity:** High fuzzy text similarity on merchant names.

The matcher uses field aliases (e.g., checking `amount`, `net_amount`, `credit`, `credit_amount` for bank amounts) to handle schema variations gracefully. Candidate generation is separate from final decision making to decouple "finding options" from "authorizing options."

---

## 11. Scoring Engine

Implemented in `engine/scorer.py`.

The scorer calculates a deterministic `overall_score` (0.0 to 1.0) based on weighted signals:

| Signal | Weight | Role in Reconciliation |
|---|---|---|
| Reference | 30% | Strongest deterministic link (`_text_score`). |
| Amount | 25% | Ensures financial exactness (or handles variance). |
| Date | 15% | Linear decay based on day difference (max 3 days). |
| Merchant | 15% | Fuzzy token similarity (`token_set_ratio`). |
| Invoice | 15% | Supplemental identifier. |

**Handling Mismatches/Missing Fields:** The system gracefully handles missing values by reducing the available weight denominator so records aren't unfairly penalized for missing optional data.

---

## 12. Policy Engine

Implemented in `engine/policy.py`.

The policy engine takes the `overall_score` and enforces strict business rules. 

**Decision States:**
- `AUTO_MATCH`: Safe to reconcile without human touch.
- `AI_REVIEW`: Ambiguous, send to AI agent.
- `HUMAN_REVIEW`: Send directly to human (score too low).
- `EXCEPTION`: Critical data missing or blocked.

**Thresholds:**
- Auto-Match: `>= 0.95`
- AI Review: `>= 0.85`
- Amount Variance Tolerance: `0.01`

**Blockers (Immediate Exceptions/Human Review):**
- `missing_source_record`: A required settlement or bank transaction record is missing.
- `multiple_viable_candidates`: To prevent guessing.
- `duplicate_candidate`: A duplicate bank candidate was detected.
- `amount_variance_above_tolerance`: Amount variance exceeds the configured tolerance.

---

## 13. AI Reconciliation Agent

Implemented in `ai/agent.py` and `ai/prompts.py`.

- **Purpose:** Analyze ambiguous cases that fall into the `[0.85, 0.95)` score band.
- **Inputs:** The specific Payment, Settlement, scoped Bank Candidates, and deterministic scores.
- **Prompt Strategy:** The prompt strictly forbids financial arithmetic and commands the model to rely only on the provided JSON evidence.
- **Output:** A structured JSON object describing the decision, confidence, and reasoning.
- **Validation:** Pydantic validation ensures the JSON conforms precisely to the required schema.
- **Error/Retry Behavior:** If the API fails or outputs invalid JSON, it retries exactly once.
- **Fallback:** If it fails again, it degrades gracefully to a `REVIEW` state (`ai_api_error` or `ai_validation_error`), ensuring no data is lost.
- **Candidate Restrictions:** The AI can only select a bank transaction ID that was supplied in the candidates list.

---

## 14. AI Provider Details

- Provider: **Groq**
- Model: **`openai/gpt-oss-120b`**

We chose Groq for its extreme inference speed, which is critical for processing hundreds of reconciliation records quickly. The model provides excellent zero-shot reasoning for structured text.

We deliberately do **not** use fine-tuning, vector databases, RAG, tool calling, function calling, or autonomous browsing. All contextual data is provided deterministically via the engine.

---

## 15. Structured Output

Implemented in `ai/schemas.py`.

We do not accept free-form text from the LLM. We enforce a strict Pydantic JSON schema (`AIReconciliationDecision`):

- `decision`: "MATCH", "REVIEW", or "EXCEPTION"
- `confidence`: Float (0.0 to 1.0)
- `reason_codes`: Array of strings
- `explanation`: Human-readable rationale
- `missing_evidence`: Array of strings detailing what data would have helped
- `selected_bank_transaction_id`: The chosen candidate ID (Nullable if REVIEW/EXCEPTION)

Structured output is crucial because downstream systems (the Policy Engine and the UI) require predictable keys and types. The strict JSON schema uses `extra="forbid"` to reject hallucinated properties.

---

## 16. Candidate Validation

The system enforces that AI candidate selection is restricted to the supplied candidate set.

**Example:**
- Allowed candidates supplied to AI: `BANK-0051`, `BANK-0052`
- AI responds with: `BANK-9999` (Invalid)

When AI selects an unknown candidate, the Policy Engine catches the violation, applies the `ai_selected_unknown_candidate` blocked condition, and routes the transaction to `HUMAN_REVIEW`.

---

## 17. AI vs Policy Authorization

**Models interpret. Rules authorize.**

AI recommendation ≠ final authorization. This distinction is critical in finance to prevent catastrophic automated errors.

**Example Workflow:**
Deterministic evidence → AI recommendation (MATCH) → Candidate Validation (OK) → Policy Validation (OK) → Final decision (AUTO_MATCH).

Even if the AI returns `MATCH` with `1.0` confidence, it does not bypass policy. The Policy Engine verifies the underlying deterministic score was eligible for AI override before accepting the recommendation.

---

## 18. Failure Recovery

The system is designed to fail conservatively instead of failing open. Handled scenarios:
- **API Timeout / Auth Failure:** Handled by `_classify_failure`. Routes to `HUMAN_REVIEW` with code `ai_timeout` or `ai_api_error`.
- **Validation Errors (Malformed JSON):** Routes to `HUMAN_REVIEW` with code `ai_validation_error`.
- **Missing Source Data:** Caught deterministically before AI is invoked; marked as `EXCEPTION`.
- **Per-record exceptions:** Handled gracefully; one bad model call or processing exception is isolated to its record (`processing_error`).

---

## 19. Audit Trail

Every transaction produces an immutable `AuditEvent`. 
Financial systems require absolute auditability. The audit trail captures:
- Deterministic scores, matching signals, and evidence count.
- Whether AI was used, the model name, and AI confidence.
- The exact explanation and reason codes provided by the AI.
- The chosen candidate.
- The final policy decision that authorized the outcome.

This connects the deterministic evidence directly to the AI's reasoning and the final outcome, ensuring analysts can always see exactly *why* a decision was made.

---

## 20. Dashboard

Implemented in `app.py`.

The Streamlit dashboard is the user-facing product, providing:
- **System Status:** Real-time visibility into engine and AI availability.
- **KPI Cards:** Displaying match rate, precision, exceptions, and AI handoffs.
- **Charts:** Visual distributions of decisions and top exception reasons.
- **Reconciliation Results:** A filterable and searchable data table of all processed records.
- **Exception Investigation:** A split-view panel showing Transaction Evidence, Deterministic Analysis, AI Analysis, and Final Policy Decision side-by-side.
- **Audit Trail:** Expandable rows showing the exact lifecycle of every payment.
- **Ask LedgerPilot:** A read-only analytical chat interface.

---

## 21. Ask LedgerPilot

The "Ask LedgerPilot" feature is a read-only controller.
- **Context Construction:** It receives bounded structured context from the current run (metrics, top exception reasons, records).
- **Constraints:** The prompt strictly grounds the LLM to only use the provided JSON context. It is forbidden from modifying records, decisions, or policy.
- **Failure Behavior:** If the API fails or there is insufficient evidence, it gracefully returns: "Insufficient evidence in the current reconciliation run."

---

## 22. Synthetic Dataset

- **Size:** 100 records.
- **Categories:** Standard exact matches, date shifts, missing references, typos, exceptions.
- **Ambiguous Records:** IDs `PAY-0051` through `PAY-0060` are specifically engineered with complex ambiguities.
- **Ground Truth:** Answer key matching Payment IDs to expected Bank IDs and statuses.

Intentionally ambiguous cases are crucial for validating AI behavior. If the dataset only contained exact matches, the AI would never be invoked.

---

## 23. Evaluation Framework

Implemented in `evaluation/evaluator.py` and `evaluation/metrics.py`.

The evaluation framework runs the real engine and measures accuracy objectively.
- **Normalization:** Flattens engine result buckets into one evaluation record per payment.
- **Ground Truth Loading:** Loads `ground_truth.csv`.
- **Comparison:** Cross-checks actual output against expected output. Rejects missing, unexpected, or duplicate IDs.
- **Correct Match:** Constitutes predicting `AUTO_MATCH` AND matching the exact expected Bank ID.
- **Metrics Calculation:** Calculates precision, recall, false auto-match rate, match rate, and exception rate specifically tailored for the LedgerPilot workflow.

---

## 24. Final Measured Results

Use ONLY these verified current metrics from the repository's evaluation layer (`FINAL_RESULTS.md` / `evaluator.py`).

| Metric | Result | Meaning |
|---|---:|---|
| **Total Records** | 100 | The dataset size. |
| **Matched** | 66 | Total records securely auto-matched. |
| **Match Rate** | 66.00% | Percentage requiring zero human touch. |
| **AI Assisted** | 10 | Ambiguous cases resolved successfully by AI. |
| **Human Review** | 26 | Safely routed to humans due to policy blockers. |
| **Exceptions** | 8 | Missing data or severe variances. |
| **Exception Rate** | 8.00% | Percentage of severe failures. |
| **Precision** | 98.48% | Accuracy of the matches made (only 1 false positive). |
| **Recall** | 92.86% | How many of the true matches we successfully found. |
| **False Auto-Match**| 1.52% | The critical risk metric (kept extremely low). |
| **Automated Tests** | 37 passed | Pytest suite ensuring engine integrity. |

*LedgerPilot is a highly accurate prototype, not a production-ready enterprise product.*

---

## 25. Real-World Users

**Who Uses LedgerPilot?**
- **Finance Operations Analysts:** Spend less time on tedious manual matching; focus on resolving the 8 exceptions.
- **Reconciliation Analysts:** Can trust the system's `AUTO_MATCH` because it has a 98.48% precision rate.
- **Payment Operations Teams:** Can investigate discrepancies efficiently using the structured UI.
- **Finance Controllers:** Gain visibility and auditability over the entire reconciliation pipeline.

*Note: These represent potential/target users for this product class, not current customers.*

---

## 26. Real-World Impact

**Demonstrated Capability:**
- Automatically matches 66% of transactions safely.
- Resolves complex ambiguities with AI.
- Maintains a 1.52% false auto-match rate.

**Expected Real-World Impact:**
- Reduced repetitive reconciliation effort for finance teams.
- Faster exception investigation due to the split-view dashboard.
- Safer AI adoption in finance through strict policy constraints.
- Improved analyst productivity.

---

## 27. Business Value

Finance teams care about operational efficiency, but they care about **control and auditability** even more. 

The primary business value is the **trade-off**: More conservative review is preferable to unsafe automation. By enforcing strict policy validation over AI recommendations, LedgerPilot scales operational efficiency while minimizing the risk of accounting errors or lost revenue.

---

## 28. Tech Stack

- **Python:** Core language for the engine and application.
- **Groq:** Lightning-fast AI inference provider.
- **openai/gpt-oss-120b:** The LLM powering the `ReconciliationAgent`.
- **Pandas:** Tabular data processing and normalization.
- **Pydantic:** Data validation and strictly typed structured JSON outputs.
- **python-dotenv:** Environment variable management.
- **Streamlit:** Rapid UI prototyping for the dashboard (`app.py`).
- **Pytest:** Comprehensive testing framework (`tests/`).
- **Git / GitHub:** Version control and repository hosting.
- **Streamlit Community Cloud:** Public deployment platform.

---

## 29. Project Structure

```text
LedgerPilot/
├── app.py                     # Streamlit web application & UI components
├── requirements.txt           # Python dependencies
├── FINAL_RESULTS.md           # Benchmark summary
├── engine/                    # Deterministic logic layer
│   ├── matcher.py             # Candidate generation logic
│   ├── normalizer.py          # String/date/amount cleaning logic
│   ├── scorer.py              # Weighted signal scoring logic
│   ├── policy.py              # Business rules and authorization logic
│   └── reconciler.py          # End-to-end orchestration logic
├── ai/                        # Agentic logic layer
│   ├── agent.py               # Groq API integration and error handling
│   ├── prompts.py             # Versioned prompt definitions
│   ├── run_report.py          # Helper to inspect AI-assisted cases
│   └── schemas.py             # Pydantic structured output definitions
├── data/                      # CSV datasets
│   ├── payments.csv, settlements.csv, bank_transactions.csv
│   └── ground_truth.csv       # Evaluation answer key
├── db/                        # Database utilities (future scope)
│   └── database.py
├── evaluation/                # Performance measurement
│   ├── evaluator.py           # Ground-truth comparison logic
│   └── metrics.py             # Precision/Recall math
└── tests/                     # 37 passing unit & integration tests
```

---

## 30. Development Planning

The project evolved logically from core problem analysis to a fully integrated AI application:

Problem analysis → architecture → data design → deterministic engine → scoring → policy → AI agent → structured outputs → safety → evaluation → dashboard → controller → failure handling → deployment.

---

## 31. Phase-by-Phase Implementation

- **Phase 1 — Problem Analysis:** Identified the need for safe AI reconciliation.
- **Phase 2 — Architecture:** Designed the deterministic-first pipeline.
- **Phase 3 — Dataset:** Engineered 100 cases, including controlled ambiguities (`PAY-0051`-`PAY-0060`).
- **Phase 4 — Normalization:** Built `normalizer.py` to strip noise.
- **Phase 5 — Matching:** Built `matcher.py` for multi-stage candidate generation.
- **Phase 6 — Scoring:** Built `scorer.py` for weighted signal evaluation.
- **Phase 7 — Policy:** Built `policy.py` to enforce thresholds and blockers.
- **Phase 8 — AI Agent:** Integrated Groq and `openai/gpt-oss-120b` in `agent.py`.
- **Phase 9 — Structured Output:** Enforced Pydantic schemas in `schemas.py`.
- **Phase 10 — AI Safety:** Added candidate validation and fallback logic.
- **Phase 11 — Evaluation:** Built `evaluator.py` to prove measurable accuracy.
- **Phase 12 — Dashboard:** Built the Streamlit UI in `app.py`.
- **Phase 13 — Controller:** Added the read-only "Ask LedgerPilot" feature.
- **Phase 14 — Final Testing:** Achieved 37 passing tests.
- **Phase 15 — Deployment:** Hosted on Streamlit Community Cloud.

---

## 32. Engineering Decisions

- **Decision: Deterministic-first architecture**
  - *Reason:* LLMs are slow and expensive; 80% of matches are obvious.
  - *Benefit:* Fast, cheap, safe.
- **Decision: AI only for ambiguity**
  - *Reason:* Limits LLM hallucinations to a constrained subset of data.
  - *Benefit:* Reduces risk.
- **Decision: Candidate validation**
  - *Reason:* AI cannot invent candidates.
  - *Benefit:* Guarantees the matched bank transaction actually exists.
- **Decision: Structured output (Pydantic)**
  - *Reason:* Downstream systems need JSON, not prose.
  - *Benefit:* Reliable parsing and validation.
- **Decision: Conservative fallback**
  - *Reason:* APIs fail, models hallucinate.
  - *Benefit:* Safely degrades to `HUMAN_REVIEW`.

---

## 33. Testing Strategy

Run the complete test suite:
```bash
pytest tests/
```
**Result:** 37 passed.

The testing strategy covers:
- **`test_matching.py`:** Verifies candidate generation stages.
- **`test_metrics.py`:** Verifies mathematical correctness of evaluation metrics.
- **`test_ai_safety.py`:** Explicitly verifies that the system handles API failures, invalid JSON, and hallucinated candidates by reverting to HUMAN_REVIEW, ensuring safety.

---

## 34. Edge Cases and Failure Scenarios

Tested and handled edge cases:
- **Missing source record:** Handled deterministically (`missing_source_record`); marked as `EXCEPTION`.
- **Multiple candidates:** Handled by policy (`multiple_viable_candidates`); marked as `HUMAN_REVIEW`.
- **Candidate mismatch (hallucination):** Handled by validation (`ai_selected_unknown_candidate`).
- **API failure / Timeout:** Handled by `agent.py` fallback (`ai_api_error` or `ai_timeout`).
- **Invalid structured output:** Caught by Pydantic; triggers fallback (`ai_validation_error`).

---

## 35. Local Setup

Clone the repository and set up your environment:

```bash
# 1. Clone repository
git clone https://github.com/your-username/LedgerPilot.git
cd LedgerPilot

# 2. Create virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
# Create a .env file and add your Groq API key
echo "GROQ_API_KEY=your_groq_api_key" > .env

# 5. Run tests
pytest tests/

# 6. Run evaluation benchmark
python -m evaluation.evaluator

# 7. Launch Streamlit Dashboard
streamlit run app.py
```

---

## 36. Configuration

- **Environment Variables:** `GROQ_API_KEY` (required for AI).
- **Requirements:** Defined in `requirements.txt`.
- **Secrets:** Keep your API keys secure. Do not commit `.env`.

---

## 37. Deployment

LedgerPilot is deployed on **Streamlit Community Cloud**.
- **Entrypoint:** `app.py`
- **Secrets:** `GROQ_API_KEY` is securely injected via Streamlit Secrets Management.
- `.env` is intentionally listed in `.gitignore` to prevent secret leakage.

---

## 38. Security

- Environment-based secret management.
- `.gitignore` prevents hardcoded API keys.
- Candidate restrictions prevent malicious or hallucinated data entry.
- Policy controls ensure AI cannot blindly authorize transactions.
- Read-only controller prevents prompt-injected data modification.
- Conservative failure defaults to safe states.

---

## 39. Demo Walkthrough (For Hackathon Judges)

1. **Open Dashboard:** Show the clean, operational UI.
2. **Run Reconciliation:** Click the button to process the 100 records. Explain that the deterministic engine handles the bulk while the AI handles edge cases.
3. **Show KPIs:** Point out the 66% Match Rate and the 10 AI-assisted cases. Highlight the 98.48% Precision (Safety).
4. **Show Normal Match:** Filter for `AUTO_MATCH` to show how fast deterministic rules work.
5. **Show AI-Assisted Case:** Filter for `AI Used = Yes`. Pick a record.
6. **Explain Deterministic Score:** Open the case in the Investigation panel. Show the underlying score (e.g., `0.88`).
7. **Show AI Recommendation:** Read the AI's explanation of *why* it matched the ambiguous text.
8. **Show Final Policy Decision:** Show that Policy authorized the AI's recommendation.
9. **Show Exception:** Filter for `EXCEPTION` to show how severe mismatches are blocked.
10. **Show Audit Trail:** Expand an audit row to prove full traceability.
11. **Use Ask LedgerPilot:** Type "Why are there 8 exceptions?" to demonstrate the read-only grounded controller.
12. **Explain Failure Recovery:** Discuss how the system degrades safely if Groq goes down.

---

## 40. Hackathon Judging Strategy

- **Problem Taste:** Demonstrates a real-world, high-value financial operations problem (reconciliation).
- **Build Quality:** Highly modular, tested (37 passing tests), and strictly typed codebase with a clean UI.
- **AI Judgment:** Uses AI *only* where necessary (ambiguity), constrained by strict deterministic bounds.
- **Failure Recovery:** Implements retry and fallback logic to guarantee zero data loss upon API failure.

---

## 41. Limitations

Current limitations of this prototype:
- Uses a synthetic dataset.
- Prototype deployment on Streamlit Community Cloud.
- No live bank integration.
- No live payment provider integration.
- No production ERP integration.
- No enterprise authentication.
- No production approval workflow.
- Limited persistence (in-memory processing).
- Prototype-scale evaluation (100 records).

---

## 42. Future Roadmap

**Future Scope (Not currently implemented):**
- Payment gateway integrations (Stripe, PayPal).
- Banking APIs (Plaid).
- ERP/accounting systems integration.
- Human approval queues with maker-checker workflows.
- Persistent audit database.
- Role-based access control (RBAC).
- Advanced settlement logic (refunds/chargebacks).
- Multi-currency support.

---

## 43. Known Trade-Offs

- **Deterministic first vs maximum automation:** We chose safety over maximum automation, resulting in a 66% match rate rather than a dangerous 95% match rate.
- **AI assistance vs cost/latency:** AI is invoked only for borderline cases to minimize API costs and processing latency.
- **Conservative review vs match rate:** We accept a higher manual review rate to keep the false auto-match risk extremely low (1.52%).
- **Synthetic data vs production realism:** We used synthetic data to guarantee control over ambiguity and evaluate the agent safely.

---

## 44. FAQ

**Q: What is LedgerPilot?**
A: A web-based AI Finance Controller for transaction reconciliation.

**Q: Is it a web app or an AI agent?**
A: Both. The Streamlit web app is the operational interface, while the `ReconciliationAgent` is the reasoning component operating inside the data workflow.

**Q: Where is the AI agent implemented?**
A: `ai/agent.py`.

**Q: Why call it an agent?**
A: It evaluates ambiguous evidence, produces a structured recommendation, and participates in a larger workflow, unlike a generic chatbot.

**Q: Is it fully autonomous?**
A: No. The deterministic Policy Engine has final authorization.

**Q: When is AI invoked?**
A: Only for ambiguous cases (scores between 0.85 and 0.95).

**Q: Can AI invent candidates or override policy?**
A: No. The AI must select from a pre-validated candidate list, and the Policy Engine double-checks all AI outputs.

**Q: What happens if AI fails?**
A: The system falls back conservatively, marking the record for `HUMAN_REVIEW` or `EXCEPTION`.

**Q: How are decisions audited?**
A: A full `AuditEvent` is generated per transaction.

**Q: What model is used?**
A: `openai/gpt-oss-120b` via Groq.

**Q: How many records were evaluated?**
A: 100 records.

**Q: What were the final metrics?**
A: 66% match rate, 98.48% precision, 10 AI-assisted cases.

---

## 45. Final Project Status

| Category | Status |
|---|---|
| Problem analysis | ✅ Complete |
| Dataset | ✅ Complete |
| Normalization | ✅ Complete |
| Matching | ✅ Complete |
| Scoring | ✅ Complete |
| Policy | ✅ Complete |
| AI Agent | ✅ Complete |
| Structured output | ✅ Complete |
| Candidate validation | ✅ Complete |
| Failure recovery | ✅ Complete |
| Audit | ✅ Complete |
| Evaluation | ✅ Complete |
| Dashboard | ✅ Complete |
| Controller | ✅ Complete |
| Testing | ✅ Complete |
| Deployment | ✅ Complete |
