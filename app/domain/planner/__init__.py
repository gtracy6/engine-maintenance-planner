"""
12-month supply/demand simulation with optimised fleet reassignment.

Simulation order each month:
  A. Process returns  → optimise fleet assignment → update engine rates
  B. Check triggers   → operational engines hitting threshold enter shop
  C. Count supply     → per fleet, after A+B
  D. Apply utilisation → accrue cycles / deplete RUL on operational engines
  E. Record snapshots
  F. Record fleet balances

Sub-modules
-----------
state       — _Eng dataclass, rate helpers, state initialisation, snapshots
simulation  — forward lookahead (_forward_simulate)
assignment  — greedy fleet reassignment (_optimise_assignment)
metrics     — recommendation generation (_build_recommendations)
"""

from __future__ import annotations

from app.core.config import MONTH_NAMES
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

from .assignment import _optimise_assignment
from .metrics import _build_recommendations
from .state import _Eng, _init_states, _rates


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
