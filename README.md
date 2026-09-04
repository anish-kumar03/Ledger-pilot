# LEDGER PILOT - AI FINANCE CONTROLLER 

> **Models interpret. Rules authorize.**

LedgerPilot is an AI-powered finance operations controller designed to reconcile **payments, settlements, and bank transactions** across multiple data sources.

Instead of allowing an LLM to directly decide financial outcomes, LedgerPilot combines:

- deterministic reconciliation
- candidate matching
- weighted scoring
- policy controls
- AI reasoning for ambiguous cases
- candidate validation
- structured outputs
- exception handling
- audit trails
- measurable evaluation
- an interactive Streamlit dashboard

The result is a controlled finance-ops workflow where AI is used **only where it adds judgment**, while deterministic rules retain authority over the final decision.

---

## Live Demo

**Streamlit App:**  
`https://ledgerpilot.streamlit.app/`

**GitHub Repository:**  
`PASTE_YOUR_GITHUB_REPOSITORY_URL_HERE`

---

# 1. Problem Statement

Finance operations teams routinely need to reconcile records across multiple sources:

- customer payments
- payment settlements
- bank transactions
- invoices
- merchant information
- transaction references

The basic task sounds simple:

> "Which payment corresponds to which settlement and which bank transaction?"

In practice, financial reconciliation becomes difficult because real-world records are often:

- inconsistent in formatting
- missing fields
- delayed across systems
- duplicated
- partially populated
- slightly different in amounts
- different in merchant naming
- different in transaction dates
- ambiguous between multiple plausible candidates

A simple exact-match system fails when data becomes messy.

A fully autonomous LLM system introduces a different risk: the model may make a plausible-looking but financially incorrect decision.

LedgerPilot addresses both problems.

---

# 2. Razorpay Hackathon — Track 04

LedgerPilot was built for the **Razorpay Hackathon, Track 04: AI Finance Controller**.

The track asks builders to create an agent that closes a finance-operations loop across a synthetic batch of 50+ records, reports measurable reconciliation performance, and honestly handles records that cannot be resolved.

The track emphasizes:

- throughput
- measured accuracy
- meaningful exception handling
- practical finance operations
- trustworthy AI judgment

LedgerPilot directly targets this requirement through a multi-source reconciliation workflow.

## Track Alignment

| Track Requirement | LedgerPilot Implementation |
|---|---|
| Finance operations workflow | Payment → settlement → bank reconciliation |
| 50+ synthetic records | 100-record evaluation dataset |
| Automated reconciliation | Deterministic candidate matching and scoring |
| AI judgment | Groq-powered reasoning for ambiguous cases |
| Measured accuracy | Precision, recall, match rate, false auto-match |
| Exception handling | Human review and explicit exception buckets |
| Failure recovery | Conservative AI fallback to review |
| Auditability | Structured audit events for every processed payment |
| Working agent | End-to-end Streamlit finance controller |
| Practical user value | Reduces manual reconciliation effort while controlling AI risk |

---

# 3. Why This Problem Matters

Reconciliation is not simply a data-matching problem.

It is a **verification and decision-control problem**.

A finance operator needs to know:

1. What records are being compared?
2. Which candidate appears most likely?
3. Why was that candidate selected?
4. How strong is the evidence?
5. Was AI involved?
6. What did the AI recommend?
7. Did policy allow the recommendation?
8. What happens when the evidence is insufficient?
9. Can the decision be audited later?

LedgerPilot is designed around these questions.

---

# 4. Core Product Idea

The core principle is:

> **Models interpret. Rules authorize.**

The LLM is not treated as the final authority.

Instead:

```text
Raw Financial Records
        ↓
Normalization
        ↓
Candidate Generation
        ↓
Deterministic Scoring
        ↓
Policy Engine
        ↓
 ┌──────────────┬──────────────┬──────────────┐
 ↓              ↓              ↓
AUTO_MATCH   AI_REVIEW      EXCEPTION
                ↓
            Groq AI Agent
                ↓
       Structured Decision
                ↓
       Candidate Validation
                ↓
        Policy Validation
                ↓
          Final Decision
                ↓
           Audit Trail
                ↓
       Evaluation Dashboard


# Understanding LedgerPilot: Web Application vs AI Agent

A key distinction in LedgerPilot is the difference between the **web application** and the **AI agent**.

LedgerPilot is best described as:

> **A web-based AI Finance Controller that contains an AI-powered reconciliation agent inside a deterministic finance-operations workflow.**

The Streamlit application is the **user-facing product and operational interface**.

The `ReconciliationAgent` is the **AI reasoning component** that interprets ambiguous financial evidence.

These are complementary parts of the same system, but they are not the same thing.

---

## 1. What Did We Actually Build?

LedgerPilot consists of three major layers:

```text
┌───────────────────────────────────────────────────────┐
│                 WEB APPLICATION                      │
│                                                       │
│              Streamlit — LedgerPilot                 │
│                                                       │
│ Dashboard | Results | Exceptions | Audit | Q&A        │
└───────────────────────┬───────────────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────────────┐
│              ORCHESTRATION & CONTROL                  │
│                                                       │
│         ReconciliationEngine + Policy Engine          │
│                                                       │
│ Normalize → Match → Score → Decide → Validate         │
└───────────────────────┬───────────────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────────────┐
│                    AI AGENT                           │
│                                                       │
│              ReconciliationAgent                      │
│                        │                              │
│                        ▼                              │
│                 Groq / GPT-OSS-120B                  │
│                        │                              │
│                        ▼                              │
│              Structured AI Decision                   │
└───────────────────────────────────────────────────────┘
