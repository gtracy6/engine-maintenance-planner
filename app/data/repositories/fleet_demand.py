"""Monthly engine demand schedule per fleet, driven by ScenarioConfig."""

from datetime import UTC, datetime

from app.core.config import MONTH_NAMES
from app.core.engine_config import ScenarioConfig


def _demand_tier(demand: int, schedule: list[int]) -> str:
    """Classify demand as high/medium/low relative to the fleet's own annual range."""
    min_d = min(schedule)
    max_d = max(schedule)
    spread = max_d - min_d or 1
    normalised = (demand - min_d) / spread
    if normalised >= 0.67:
        return "high"
    elif normalised >= 0.33:
        return "medium"
    return "low"


def get_demand_context(
    fleet: str,
    scenario: ScenarioConfig,
    reference_date: datetime | None = None,
) -> dict:
    """
    Return demand context for a fleet under a given scenario.

    Keys:
        fleet                 : str
        current_month         : str   e.g. "Apr"
        current_month_demand  : int
        next_month_demand     : int
        demand_tier           : str   high / medium / low
        upcoming_peak         : bool  demand rises in next 2 months
        maintenance_window    : bool  at or near annual low (good time for shop)
        monthly_schedule      : dict  full-year {month_name: demand}
    """
    fleet_cfg = scenario.fleets[fleet]
    schedule = fleet_cfg.monthly_demand

    if reference_date is None:
        reference_date = datetime.now(UTC)

    month_idx = reference_date.month - 1
    next_idx = (month_idx + 1) % 12
    two_ahead_idx = (month_idx + 2) % 12

    current = schedule[month_idx]
    next_month = schedule[next_idx]
    two_ahead = schedule[two_ahead_idx]

    tier = _demand_tier(current, schedule)
    fleet_min = min(schedule)
    upcoming_peak = (next_month > current) or (two_ahead > current)
    maintenance_window = current <= fleet_min + 1

    return {
        "fleet": fleet,
        "current_month": MONTH_NAMES[month_idx],
        "current_month_demand": current,
        "next_month_demand": next_month,
        "demand_tier": tier,
        "upcoming_peak": upcoming_peak,
        "maintenance_window": maintenance_window,
        "monthly_schedule": {MONTH_NAMES[i]: schedule[i] for i in range(12)},
    }
