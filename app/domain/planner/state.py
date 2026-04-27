from __future__ import annotations

from dataclasses import dataclass, field

from app.core.engine_config import EngineTypeConfig, ScenarioConfig
from app.schemas.plan import PoolPlanInput


@dataclass
class _Eng:
    engine_id: str
    original_fleet: str
    current_fleet: str
    cycles: float
    rul: float
    status: str  # "operational" | "in_maintenance"
    return_month: int | None
    monthly_cycles: float
    monthly_rul_drop: float
    shop_visits: int = 0
    timeline: list = field(default_factory=list)


def _rates(
    fleet: str, scenario: ScenarioConfig, engine_cfg: EngineTypeConfig
) -> tuple[float, float]:
    mc = scenario.fleets[fleet].annual_utilisation / 12
    return mc, mc / engine_cfg.max_cycles_between_shop


def _init_states(
    plan: PoolPlanInput, scenario: ScenarioConfig, engine_cfg: EngineTypeConfig
) -> list[_Eng]:
    states = []
    for e in plan.engines:
        mc, mrd = _rates(e.fleet, scenario, engine_cfg)
        return_month = (
            (e.months_remaining_in_shop if e.months_remaining_in_shop > 0 else 1)
            if e.status == "in_maintenance"
            else None
        )
        states.append(
            _Eng(
                engine_id=e.engine_id,
                original_fleet=e.fleet,
                current_fleet=e.fleet,
                cycles=float(e.cycles_since_shop),
                rul=e.remaining_useful_life,
                status=e.status,
                return_month=return_month,
                monthly_cycles=mc,
                monthly_rul_drop=mrd,
            )
        )
    return states


def _snapshot(states: list[_Eng]) -> list[dict]:
    return [
        {
            "id": s.engine_id,
            "fleet": s.current_fleet,
            "cycles": s.cycles,
            "rul": s.rul,
            "status": s.status,
            "return_month": s.return_month,
        }
        for s in states
    ]
