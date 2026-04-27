from __future__ import annotations

from copy import deepcopy

from app.core.engine_config import EngineTypeConfig, ScenarioConfig

from .simulation import _forward_simulate
from .state import _Eng, _snapshot


def _optimise_assignment(
    engine_id: str,
    states: list[_Eng],
    current_month: int,
    total_months: int,
    shop_duration: int,
    start_month: int,
    scenario: ScenarioConfig,
    engine_cfg: EngineTypeConfig,
) -> tuple[str, str]:
    """
    Score every candidate fleet via forward simulation and pick the one that
    maximises total satisfied demand. Returns (best_fleet, reason_string).
    """
    all_fleets = list(scenario.fleets.keys())
    base_snap = _snapshot(states)
    scores: dict[str, int] = {}

    for candidate in all_fleets:
        trial = deepcopy(base_snap)
        for s in trial:
            if s["id"] == engine_id:
                s.update(fleet="___", status="operational", cycles=0.0, rul=1.0, return_month=None)
                s["fleet"] = candidate
        scores[candidate] = _forward_simulate(
            trial, current_month, total_months, shop_duration, start_month, scenario, engine_cfg
        )

    best_fleet = max(scores, key=scores.__getitem__)
    sorted_others = sorted(
        ((f, v) for f, v in scores.items() if f != best_fleet),
        key=lambda x: -x[1],
    )
    reason = (
        f"Optimised: {best_fleet} yields {scores[best_fleet]} satisfied-demand units "
        f"(vs {', '.join(f'{f}:{v}' for f, v in sorted_others)})"
    )
    return best_fleet, reason
