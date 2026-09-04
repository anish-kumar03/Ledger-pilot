from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AIReconciliationDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["MATCH", "REVIEW", "EXCEPTION"]
    confidence: float = Field(ge=0.0, le=1.0)
    reason_codes: list[str]
    explanation: str
    missing_evidence: list[str]
    selected_bank_transaction_id: str | None

    @model_validator(mode="before")
    @classmethod
    def preserve_nullable_omission_compatibility(cls, values):
        """Keep existing REVIEW/EXCEPTION callers compatible with the required schema field."""
        if isinstance(values, dict) and "selected_bank_transaction_id" not in values:
            values = {**values, "selected_bank_transaction_id": None}
        return values

    @model_validator(mode="after")
    def validate_selected_candidate(self) -> "AIReconciliationDecision":
        """Require a selected bank candidate for a MATCH recommendation."""
        if self.decision == "MATCH" and not self.selected_bank_transaction_id:
            raise ValueError("selected_bank_transaction_id is required when decision is MATCH")
        return self