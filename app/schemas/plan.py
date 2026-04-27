from pydantic import BaseModel, field_validator

from app.schemas.engine import EnginePoolEntry


class PoolPlanInput(BaseModel):
    engines: list[EnginePoolEntry]
    shop_visit_duration: int = 2  # months in maintenance (default 2)
    start_month: int = 1  # calendar month simulation starts (1=Jan)
    engine_type: str = "v2500"  # matches config/engine_types/<name>.yaml
    scenario: str = "default"  # matches config/scenarios/<name>.yaml

    @field_validator("shop_visit_duration")
    @classmethod
    def duration_in_range(cls, v: int) -> int:
        if not 1 <= v <= 12:
            raise ValueError("shop_visit_duration must be between 1 and 12")
        return v

    @field_validator("start_month")
    @classmethod
    def month_in_range(cls, v: int) -> int:
        if not 1 <= v <= 12:
            raise ValueError("start_month must be between 1 and 12")
        return v

    @field_validator("engines")
    @classmethod
    def must_have_engines(cls, v: list) -> list:
        if not v:
            raise ValueError("engines list must not be empty")
        return v


class FleetReassignment(BaseModel):
    month: int
    calendar_month: str
    engine_id: str
    from_fleet: str
    to_fleet: str
    reason: str


class EngineMonthStatus(BaseModel):
    month: int  # simulation month 1–12
    calendar_month: str
    status: str  # operational | in_maintenance | returned_from_shop
    assigned_fleet: str  # may differ from original fleet after reassignment
    cycles_since_shop: int
    remaining_useful_life: float
    trigger_hit: bool = False
    trigger_reason: str | None = None  # rul_threshold | cycle_threshold | both
    shop_return_month: int | None = None


class FleetMonthBalance(BaseModel):
    month: int
    calendar_month: str
    fleet: str
    demand: int
    supply: int
    balance: int  # supply-demand (negative = deficit)
    deficit: bool
    engines_in_shop: int


class DeficitAlert(BaseModel):
    month: int
    calendar_month: str
    fleet: str
    demand: int
    supply: int
    shortfall: int
    severity: str  # "warning" (1-2 shortfall) | "critical" (3+)


class PlanSummary(BaseModel):
    total_engines: int
    engines_per_fleet: dict
    total_shop_visits_triggered: int
    total_deficit_months: int
    worst_fleet: str | None = None
    worst_month: str | None = None


class TwelveMonthPlan(BaseModel):
    summary: PlanSummary
    engine_timelines: dict  # engine_id -> List[EngineMonthStatus]
    fleet_balances: dict  # fleet -> List[FleetMonthBalance]
    deficit_alerts: list[DeficitAlert]
    fleet_reassignments: list[FleetReassignment]
    recommendations: list[str]
