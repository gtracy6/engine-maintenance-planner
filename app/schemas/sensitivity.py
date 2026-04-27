"""Request/response models for the sensitivity analysis endpoint."""

from pydantic import BaseModel, field_validator

from app.schemas.engine import EngineInput

# Scalar fields 
_SWEEPABLE_FIELDS = frozenset(
    {
        "rul_trigger",
        "cycle_trigger",
        "max_cycles_between_shop",
        "maintenance_base_cost",
        "maintenance_cost_per_cycle",
        "score_threshold_high",
        "score_threshold_medium",
    }
)


class SensitivityParam(BaseModel):
    field: str
    values: list[float]

    @field_validator("field")
    @classmethod
    def must_be_sweepable(cls, v: str) -> str:
        if v not in _SWEEPABLE_FIELDS:
            raise ValueError(
                f"'{v}' is not sweepable. Supported fields: {sorted(_SWEEPABLE_FIELDS)}"
            )
        return v

    @field_validator("values")
    @classmethod
    def must_have_values(cls, v: list[float]) -> list[float]:
        if not v:
            raise ValueError("values list must not be empty")
        return v


class SensitivityRequest(BaseModel):
    engine: EngineInput
    sweep: SensitivityParam


class SensitivityPoint(BaseModel):
    value: float
    priority: str
    score: int
    recommendation: str
    drivers: list[str]
    immediate_cost: int
    delay_risk_cost: int


class SensitivityResponse(BaseModel):
    engine_id: str
    engine_type: str
    scenario: str
    parameter: str
    baseline_value: float
    results: list[SensitivityPoint]
