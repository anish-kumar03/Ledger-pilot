from typing import Literal

from pydantic import BaseModel, Field


class AIReconciliationDecision(BaseModel):
    decision: Literal["MATCH", "REVIEW", "EXCEPTION"]
    confidence: float = Field(ge=0.0, le=1.0)
    reason_codes: list[str]
    explanation: str
    missing_evidence: list[str]