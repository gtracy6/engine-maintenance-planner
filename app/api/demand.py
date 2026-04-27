from fastapi import APIRouter, HTTPException

from app.core.config import MONTH_NAMES
from app.core.loader import get_scenario
from app.data.repositories.fleet_demand import get_demand_context

router = APIRouter(prefix="/demand", tags=["Demand"])


@router.get("/{fleet}")
def get_fleet_demand(fleet: str, scenario: str = "default"):
    """Return the demand context for a fleet in the current calendar month."""
    try:
        scenario_cfg = get_scenario(scenario)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    if fleet not in scenario_cfg.fleets:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown fleet '{fleet}'. Must be one of {list(scenario_cfg.fleets)}",
        )
    return get_demand_context(fleet, scenario_cfg)


@router.get("/{fleet}/{month}")
def get_fleet_demand_by_month(fleet: str, month: int, scenario: str = "default"):
    """Return the engine demand for a fleet in a specific calendar month (1=Jan)."""
    try:
        scenario_cfg = get_scenario(scenario)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    if fleet not in scenario_cfg.fleets:
        raise HTTPException(status_code=404, detail=f"Unknown fleet '{fleet}'")
    if not 1 <= month <= 12:
        raise HTTPException(status_code=400, detail="Month must be between 1 and 12")

    return {
        "fleet": fleet,
        "scenario": scenario,
        "month": MONTH_NAMES[month - 1],
        "demand": scenario_cfg.fleets[fleet].monthly_demand[month - 1],
    }
