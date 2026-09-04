from typing import Literal

from pydantic import BaseModel, Field, model_validator


class AIReconciliationDecision(BaseModel):
    decision: Literal["MATCH", "REVIEW", "EXCEPTION"]
    confidence: float = Field(ge=0.0, le=1.0)
    reason_codes: list[str]
    explanation: str
    missing_evidence: list[str]
    selected_bank_transaction_id: str | None = None

    @model_validator(mode="after")
    def validate_selected_candidate(self) -> "AIReconciliationDecision":
        """Require a selected bank candidate for a MATCH recommendation."""
        if self.decision == "MATCH" and not self.selected_bank_transaction_id:
            raise ValueError("selected_bank_transaction_id is required when decision is MATCH")
        return self