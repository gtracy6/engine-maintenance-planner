from __future__ import annotations

from copy import deepcopy

from app.core.engine_config import EngineTypeConfig, ScenarioConfig

from .state import _rates


def _forward_simulate(
    snap: list[dict],
    from_month: int,
    total_months: int,
    shop_duration: int,
    start_month: int,
    scenario: ScenarioConfig,
    engine_cfg: EngineTypeConfig,
) -> int:
    """
    Lookahead: returns total satisfied demand (sum of min(supply, demand)) from
    from_month to total_months. No recursive reassignment — O(fleets * months).
    """
    all_fleets = list(scenario.fleets.keys())
    states = deepcopy(snap)
    satisfied = 0

    for sim_month in range(from_month, total_months + 1):
        cal_idx = (start_month - 1 + sim_month - 1) % 12

        for s in states:
            if s["status"] == "in_maintenance" and s["return_month"] == sim_month:
                s["status"] = "operational"
                s["cycles"] = 0.0
                s["rul"] = 1.0
                s["return_month"] = None

        for s in states:
            if s["status"] == "operational" and (
                s["rul"] <= engine_cfg.rul_trigger or s["cycles"] >= engine_cfg.cycle_trigger
            ):
                s["status"] = "in_maintenance"
                s["return_month"] = sim_month + shop_duration

        for fleet in all_fleets:
            supply = sum(
                1 for s in states if s["status"] == "operational" and s["fleet"] == fleet
            )
            demand = scenario.fleets[fleet].monthly_demand[cal_idx]
            satisfied += min(supply, demand)

        for s in states:
            if s["status"] == "operational":
                mc, mrd = _rates(s["fleet"], scenario, engine_cfg)
                s["cycles"] = min(s["cycles"] + mc, engine_cfg.max_cycles_between_shop)
                s["rul"] = max(s["rul"] - mrd, 0.0)

    return satisfied
