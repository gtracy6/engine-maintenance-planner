"""Pydantic models for YAML-driven engine-type and fleet-scenario configs."""

from pydantic import BaseModel, field_validator


class DelayRiskMultiplier(BaseModel):
    high: float
    medium: float
    low: float

    def get(self, priority: str, default: float = 1.0) -> float:
        return getattr(self, priority, default)


class EngineTypeConfig(BaseModel):
    name: str
    max_cycles_between_shop: int
    rul_trigger: float
    cycle_trigger: int
    default_shop_visit_duration: int
    maintenance_base_cost: int
    maintenance_cost_per_cycle: int
    delay_risk_multiplier: DelayRiskMultiplier
    score_threshold_high: int
    score_threshold_medium: int


class FleetConfig(BaseModel):
    annual_utilisation: int
    utilisation_level: str
    monthly_demand: list[int]

    @field_validator("monthly_demand")
    @classmethod
    def must_have_12_months(cls, v: list[int]) -> list[int]:
        if len(v) != 12:
            raise ValueError("monthly_demand must have exactly 12 values")
        return v

    @field_validator("utilisation_level")
    @classmethod
    def must_be_valid_level(cls, v: str) -> str:
        if v not in {"low", "medium", "high"}:
            raise ValueError("utilisation_level must be one of: low, medium, high")
        return v


class ScenarioConfig(BaseModel):
    name: str
    description: str = ""
    fleets: dict[str, FleetConfig]
