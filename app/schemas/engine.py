from pydantic import BaseModel, field_validator

from app.core.config import VALID_STATUSES


class EngineInput(BaseModel):
    """Single engine state for real-time assessment."""

    engine_id: str
    engine_type: str = "v2500"  
    scenario: str = "default" 
    fleet: str
    cycles_since_shop: int
    remaining_useful_life: float  # 0～1 fraction of life remaining
    condition_score: float  #0～1 (1 = perfect)
    lease_return_due: bool
    spare_available: bool

    @field_validator("remaining_useful_life", "condition_score")
    @classmethod
    def must_be_unit_interval(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("must be between 0.0 and 1.0")
        return v

    @field_validator("cycles_since_shop")
    @classmethod
    def cycles_must_be_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("cycles_since_shop must be non-negative")
        return v


class EnginePoolEntry(BaseModel):
    """Engine state at the start of a pool planning simulation."""

    engine_id: str
    fleet: str
    cycles_since_shop: int
    remaining_useful_life: float  # 0.0–1.0
    condition_score: float  # 0.0–1.0
    status: str = "operational"  # operational, in_maintenance
    months_remaining_in_shop: int = 0

    @field_validator("remaining_useful_life", "condition_score")
    @classmethod
    def must_be_unit_interval(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("must be between 0.0 and 1.0")
        return v

    @field_validator("status")
    @classmethod
    def status_must_be_valid(cls, v: str) -> str:
        if v not in VALID_STATUSES:
            raise ValueError(f"status must be one of {VALID_STATUSES}")
        return v

    @field_validator("cycles_since_shop")
    @classmethod
    def cycles_must_be_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("cycles_since_shop must be non-negative")
        return v
