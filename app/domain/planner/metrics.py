from __future__ import annotations

from app.core.engine_config import EngineTypeConfig
from app.schemas.plan import FleetMonthBalance, FleetReassignment

from .state import _Eng


def _build_recommendations(
    fleet_balances: dict[str, list[FleetMonthBalance]],
    reassignments: list[FleetReassignment],
    states: list[_Eng],
    engine_cfg: EngineTypeConfig,
) -> list[str]:
    recs: list[str] = []
    has_deficit = any(b.deficit for bals in fleet_balances.values() for b in bals)

    if not has_deficit:
        recs.append("Pool supply meets demand across all 12 months after optimised reassignment.")
        return recs

    for fleet, bals in fleet_balances.items():
        deficit_months = [b for b in bals if b.deficit]
        if not deficit_months:
            continue
        recs.append(
            f"Fleet {fleet} has {len(deficit_months)} deficit month(s) "
            f"({', '.join(b.calendar_month for b in deficit_months)}) after reassignment. "
            f"Consider expanding the engine pool."
        )
        for b in bals:
            if b.engines_in_shop >= 2:
                recs.append(
                    f"Fleet {fleet} month {b.month} ({b.calendar_month}): "
                    f"{b.engines_in_shop} engines simultaneously in shop — stagger visits where RUL allows."
                )
                break

    peak_cal = {"Jun", "Jul", "Aug"}
    for fleet, bals in fleet_balances.items():
        for b in bals:
            if b.deficit and b.calendar_month in peak_cal:
                recs.append(
                    f"Fleet {fleet} deficit in peak month {b.calendar_month}. "
                    f"Schedule preventive shop visits in Jan–Feb to protect summer coverage."
                )
                break

    cross_fleet = [r for r in reassignments if r.from_fleet != r.to_fleet]
    if cross_fleet:
        recs.append(
            f"{len(cross_fleet)} engine(s) reassigned to a different fleet after maintenance: "
            + ", ".join(f"{r.engine_id} {r.from_fleet}→{r.to_fleet}" for r in cross_fleet)
            + "."
        )

    for s in states:
        if s.status == "operational" and s.monthly_rul_drop > 0 and s.monthly_cycles > 0:
            months_left = min(
                (s.rul - engine_cfg.rul_trigger) / s.monthly_rul_drop,
                (engine_cfg.cycle_trigger - s.cycles) / s.monthly_cycles,
            )
            if 0 < months_left <= 3:
                recs.append(
                    f"Engine {s.engine_id} (fleet {s.current_fleet}) hits threshold "
                    f"in ~{months_left:.1f} months — book MRO slot immediately."
                )

    return recs
