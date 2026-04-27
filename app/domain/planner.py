"""
12-month supply/demand simulation with optimised fleet reassignment

When an engine returns from maintenance, the planner evaluates all subfleets
via a forward lookahead simulation and assigns the engine to the fleet that
maximises total satisfied demand with an agreedy approach across all remaining months. 


Simulation order each month:
  A. Process returns  → optimise fleet assignment → update engine rates
  B. Check triggers   → operational engines hitting threshold enter shop
  C. Count supply     → per fleet, after A+B
  D. Apply utilisation → accrue cycles / deplete RUL on operational engines
  E. Record snapshots
  F. Record fleet balances
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field

from app.core.config import MONTH_NAMES
from app.core.engine_config import EngineTypeConfig, ScenarioConfig
from app.core.loader import get_engine_type, get_scenario
from app.schemas.plan import (
    DeficitAlert,
    EngineMonthStatus,
    FleetMonthBalance,
    FleetReassignment,
    PlanSummary,
    PoolPlanInput,
    TwelveMonthPlan,
)

# ── Internal mutable engine state (not exposed outside this module) ────────────


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

# month rate calc
def _rates(
    fleet: str, scenario: ScenarioConfig, engine_cfg: EngineTypeConfig
) -> tuple[float, float]:
    mc = scenario.fleets[fleet].annual_utilisation / 12
    return mc, mc / engine_cfg.max_cycles_between_shop

#state update with simulation
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


# engine state snapshot
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
    Simplified forward simulation from from_month to total_months.
    Returns total satisfied demand = sum of min(supply, demand) across all
    fleets and months. Higher is better.
    No recursive reassignment to keep lookahead O(fleets * remaining_months).
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
            supply = sum(1 for s in states if s["status"] == "operational" and s["fleet"] == fleet)
            demand = scenario.fleets[fleet].monthly_demand[cal_idx]
            satisfied += min(supply, demand)

        for s in states:
            if s["status"] == "operational":
                mc, mrd = _rates(s["fleet"], scenario, engine_cfg)
                s["cycles"] = min(s["cycles"] + mc, engine_cfg.max_cycles_between_shop)
                s["rul"] = max(s["rul"] - mrd, 0.0)

    return satisfied


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
    Try assigning the returning engine to each fleet.
    Pick the fleet that maximises total satisfied demand across remaining months.
    Returns (best_fleet, reason_string).
    """
    all_fleets = list(scenario.fleets.keys())
    base_snap = _snapshot(states)
    scores: dict[str, int] = {}

    for candidate in all_fleets:
        trial = deepcopy(base_snap)
        for s in trial:
            if s["id"] == engine_id:
                s.update(fleet="___", status="operational", cycles=0.0, rul=1.0, return_month=None)
                s["fleet"] = candidate  # separate assignment to avoid mypy complaints
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


# ── Recommendation generation ─────────────────────────────────────────────────


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


# ── Main simulation entry point ───────────────────────────────────────────────


def run_simulation(plan: PoolPlanInput) -> TwelveMonthPlan:
    engine_cfg = get_engine_type(plan.engine_type)
    scenario = get_scenario(plan.scenario)
    all_fleets = list(scenario.fleets.keys())

    states = _init_states(plan, scenario, engine_cfg)
    shop_dur = plan.shop_visit_duration
    start_month = plan.start_month
    total_months = 12

    fleet_balances: dict[str, list[FleetMonthBalance]] = {f: [] for f in all_fleets}
    reassignments: list[FleetReassignment] = []

    for sim_month in range(1, total_months + 1):
        cal_idx = (start_month - 1 + sim_month - 1) % 12
        cal_name = MONTH_NAMES[cal_idx]

        # A: Returns + optimised fleet assignment
        for s in states:
            if s.status == "in_maintenance" and s.return_month == sim_month:
                prev_fleet = s.current_fleet
                s.status = "operational"
                s.cycles = 0.0
                s.rul = 1.0
                s.return_month = None

                best_fleet, reason = _optimise_assignment(
                    s.engine_id,
                    states,
                    sim_month,
                    total_months,
                    shop_dur,
                    start_month,
                    scenario,
                    engine_cfg,
                )
                s.current_fleet = best_fleet
                s.monthly_cycles, s.monthly_rul_drop = _rates(best_fleet, scenario, engine_cfg)
                s.shop_visits += 1

                reassignments.append(
                    FleetReassignment(
                        month=sim_month,
                        calendar_month=cal_name,
                        engine_id=s.engine_id,
                        from_fleet=prev_fleet,
                        to_fleet=best_fleet,
                        reason=reason,
                    )
                )

        # B: Trigger checks
        for s in states:
            if s.status != "operational":
                continue
            rul_hit = s.rul <= engine_cfg.rul_trigger
            cycle_hit = s.cycles >= engine_cfg.cycle_trigger
            if rul_hit or cycle_hit:
                s.status = "in_maintenance"
                s.return_month = sim_month + shop_dur
                s._trigger_hit = True
                s._trigger_reason = (
                    "both"
                    if rul_hit and cycle_hit
                    else "rul_threshold" if rul_hit else "cycle_threshold"
                )
            else:
                s._trigger_hit = False
                s._trigger_reason = None

        # C: Supply count
        supply: dict[str, int] = dict.fromkeys(all_fleets, 0)
        in_shop: dict[str, int] = dict.fromkeys(all_fleets, 0)
        for s in states:
            (supply if s.status == "operational" else in_shop)[s.current_fleet] += 1

        # D: Apply utilisation
        for s in states:
            if s.status == "operational":
                s.cycles = min(s.cycles + s.monthly_cycles, engine_cfg.max_cycles_between_shop)
                s.rul = max(s.rul - s.monthly_rul_drop, 0.0)

        # E: Timeline snapshots
        for s in states:
            prev = s.timeline[-1].status if s.timeline else None
            if prev == "in_maintenance" and s.status == "operational":
                snap_status = "returned_from_shop"
            elif getattr(s, "_trigger_hit", False):
                snap_status = "in_maintenance"
            else:
                snap_status = s.status

            s.timeline.append(
                EngineMonthStatus(
                    month=sim_month,
                    calendar_month=cal_name,
                    status=snap_status,
                    assigned_fleet=s.current_fleet,
                    cycles_since_shop=int(s.cycles),
                    remaining_useful_life=round(s.rul, 4),
                    trigger_hit=getattr(s, "_trigger_hit", False),
                    trigger_reason=getattr(s, "_trigger_reason", None),
                    shop_return_month=s.return_month,
                )
            )

        # F: Fleet balances
        for fleet in all_fleets:
            demand = scenario.fleets[fleet].monthly_demand[cal_idx]
            sup = supply[fleet]
            balance = sup - demand
            fleet_balances[fleet].append(
                FleetMonthBalance(
                    month=sim_month,
                    calendar_month=cal_name,
                    fleet=fleet,
                    demand=demand,
                    supply=sup,
                    balance=balance,
                    deficit=balance < 0,
                    engines_in_shop=in_shop[fleet],
                )
            )

    # Build outputs
    deficit_alerts = sorted(
        [
            DeficitAlert(
                month=b.month,
                calendar_month=b.calendar_month,
                fleet=fleet,
                demand=b.demand,
                supply=b.supply,
                shortfall=b.demand - b.supply,
                severity="critical" if (b.demand - b.supply) >= 3 else "warning",
            )
            for fleet, bals in fleet_balances.items()
            for b in bals
            if b.deficit
        ],
        key=lambda a: (a.month, a.fleet),
    )

    engines_per_fleet = {f: sum(1 for s in states if s.original_fleet == f) for f in all_fleets}
    fleet_deficit_counts = {f: sum(1 for b in fleet_balances[f] if b.deficit) for f in all_fleets}
    worst_fleet = (
        max(fleet_deficit_counts, key=fleet_deficit_counts.__getitem__)
        if any(fleet_deficit_counts.values())
        else None
    )

    month_shortfalls: dict[int, int] = {}
    for a in deficit_alerts:
        month_shortfalls[a.month] = month_shortfalls.get(a.month, 0) + a.shortfall
    worst_sim_month = (
        max(month_shortfalls, key=month_shortfalls.__getitem__) if month_shortfalls else None
    )
    worst_month_name = (
        MONTH_NAMES[(start_month - 1 + worst_sim_month - 1) % 12] if worst_sim_month else None
    )

    return TwelveMonthPlan(
        summary=PlanSummary(
            total_engines=len(states),
            engines_per_fleet=engines_per_fleet,
            total_shop_visits_triggered=sum(s.shop_visits for s in states),
            total_deficit_months=len(deficit_alerts),
            worst_fleet=worst_fleet,
            worst_month=worst_month_name,
        ),
        engine_timelines={s.engine_id: s.timeline for s in states},
        fleet_balances=fleet_balances,
        deficit_alerts=deficit_alerts,
        fleet_reassignments=reassignments,
        recommendations=_build_recommendations(fleet_balances, reassignments, states, engine_cfg),
    )
