from datetime import UTC, datetime, timedelta

from app.core.engine_config import EngineTypeConfig, FleetConfig, ScenarioConfig
from app.core.loader import get_engine_type, get_scenario
from app.data.repositories.fleet_demand import get_demand_context
from app.schemas.assessment import (
    AssessmentResult,
    CostEstimate,
    DemandContext,
    MaintenanceForecast,
)
from app.schemas.engine import EngineInput


def forecast_maintenance(
    engine: EngineInput,
    engine_cfg: EngineTypeConfig,
    fleet_cfg: FleetConfig,
) -> MaintenanceForecast:
    annual_cycles = fleet_cfg.annual_utilisation
    monthly_cycles = annual_cycles / 12
    remaining_cycles = int(engine.remaining_useful_life * engine_cfg.max_cycles_between_shop)
    months_until_shop = remaining_cycles / monthly_cycles if monthly_cycles > 0 else float("inf")

    now = datetime.now(UTC)
    predicted_shop_date = now + timedelta(days=months_until_shop * 30.44)

    within_3 = months_until_shop <= 3
    within_6 = months_until_shop <= 6
    within_12 = months_until_shop <= 12
    within_24 = months_until_shop <= 24

    if within_3:
        note = (
            f"URGENT: Engine {engine.engine_id} projected to reach shop limits in "
            f"~{months_until_shop:.1f} months ({remaining_cycles:,} cycles remaining at "
            f"{annual_cycles:,} cycles/year for fleet {engine.fleet}). Immediate MRO slot required."
        )
    elif within_6:
        note = (
            f"Engine {engine.engine_id} requires a shop visit within 6 months "
            f"(~{months_until_shop:.1f} months, {remaining_cycles:,} cycles remaining). "
            f"Begin MRO slot reservation now."
        )
    elif within_12:
        note = (
            f"Engine {engine.engine_id} approaching shop limits within the year "
            f"(~{months_until_shop:.1f} months, {remaining_cycles:,} cycles remaining). "
            f"Include in next planning cycle."
        )
    elif within_24:
        note = (
            f"Engine {engine.engine_id} will need a shop visit in ~{months_until_shop:.1f} months "
            f"({remaining_cycles:,} cycles remaining). Monitor and plan ahead."
        )
    else:
        note = (
            f"Engine {engine.engine_id} has {remaining_cycles:,} cycles remaining "
            f"(~{months_until_shop:.1f} months at fleet {engine.fleet} utilisation). "
            f"No near-term shop action required."
        )

    return MaintenanceForecast(
        fleet=engine.fleet,
        annual_utilisation_cycles=annual_cycles,
        remaining_cycles=remaining_cycles,
        months_until_shop=round(months_until_shop, 1),
        predicted_shop_date=predicted_shop_date,
        within_3_months=within_3,
        within_6_months=within_6,
        within_12_months=within_12,
        within_24_months=within_24,
        forecast_note=note,
    )


def estimate_cost(
    engine: EngineInput,
    priority: str,
    engine_cfg: EngineTypeConfig,
) -> CostEstimate:
    immediate = engine_cfg.maintenance_base_cost + (
        engine.cycles_since_shop * engine_cfg.maintenance_cost_per_cycle
    )
    delay_risk = int(immediate * engine_cfg.delay_risk_multiplier.get(priority))

    narratives = {
        "high": "Immediate maintenance is strongly advised. Delaying significantly increases AOG and safety risk costs.",
        "medium": "Plan maintenance within the next scheduling window to avoid cost escalation.",
        "low": "Engine is within acceptable operating parameters. Continue monitoring.",
    }

    return CostEstimate(
        immediate_maintenance_cost=immediate,
        delay_risk_cost=delay_risk,
        recommendation=narratives.get(priority, narratives["low"]),
    )


def evaluate_engine(
    engine: EngineInput,
    engine_cfg: EngineTypeConfig | None = None,
    scenario: ScenarioConfig | None = None,
) -> AssessmentResult:
    if engine_cfg is None:
        engine_cfg = get_engine_type(engine.engine_type)
    if scenario is None:
        scenario = get_scenario(engine.scenario)

    fleet_cfg = scenario.fleets.get(engine.fleet)
    if fleet_cfg is None:
        raise ValueError(
            f"Fleet '{engine.fleet}' not found in scenario '{scenario.name}'. "
            f"Available: {list(scenario.fleets)}"
        )

    score = 0
    drivers: list[str] = []
    utilisation_level = fleet_cfg.utilisation_level

    # Remaining useful life
    rul = engine.remaining_useful_life
    if rul < 0.05:
        score += 5
        drivers.append("critical_rul")
    elif rul < 0.15:
        score += 4
        drivers.append("very_low_rul")
    elif rul < 0.25:
        score += 3
        drivers.append("low_rul")
    elif rul < 0.40:
        score += 1
        drivers.append("moderate_rul")

    # Cycles since shop (relative to engine type's hard limit)
    cycle_pct = engine.cycles_since_shop / engine_cfg.max_cycles_between_shop
    if cycle_pct >= 0.80:
        score += 4
        drivers.append("critical_cycle_count")
    elif cycle_pct >= 0.60:
        score += 3
        drivers.append("high_cycle_count")
    elif cycle_pct >= 0.40:
        score += 2
        drivers.append("elevated_cycle_count")
    elif cycle_pct >= 0.20:
        score += 1
        drivers.append("moderate_cycle_count")

    # Fleet utilisation tier (from scenario)
    if utilisation_level == "high":
        score += 2
        drivers.append("high_fleet_utilisation")
    elif utilisation_level == "medium":
        score += 1
        drivers.append("medium_fleet_utilisation")

    # Condition score
    cs = engine.condition_score
    if cs < 0.30:
        score += 3
        drivers.append("poor_condition")
    elif cs < 0.50:
        score += 2
        drivers.append("degraded_condition")
    elif cs < 0.70:
        score += 1
        drivers.append("fair_condition")

    # Lease constraint
    if engine.lease_return_due:
        score += 2
        drivers.append("lease_constraint")

    # Fleet monthly demand (from scenario)
    demand_ctx = get_demand_context(engine.fleet, scenario)
    if demand_ctx["demand_tier"] == "high":
        score += 2
        drivers.append("high_fleet_demand")
    elif demand_ctx["demand_tier"] == "medium":
        score += 1
        drivers.append("medium_fleet_demand")

    if demand_ctx["upcoming_peak"] and engine.remaining_useful_life < 0.30:
        score += 2
        drivers.append("upcoming_demand_peak_with_low_rul")

    if demand_ctx["maintenance_window"]:
        drivers.append("maintenance_window_available")

    # Spare availability
    if not engine.spare_available:
        score += 1
        drivers.append("no_spare")

    # Decision threshold (from engine type config)
    if score >= engine_cfg.score_threshold_high:
        action, priority = "send_to_maintenance", "high"
    elif score >= engine_cfg.score_threshold_medium:
        action, priority = "monitor_or_plan", "medium"
    else:
        action, priority = "continue_operation", "low"

    return AssessmentResult(
        engine_id=engine.engine_id,
        fleet=engine.fleet,
        engine_type=engine_cfg.name,
        scenario=scenario.name,
        utilisation_level=utilisation_level,
        recommendation=action,
        priority=priority,
        score=score,
        drivers=drivers,
        demand_context=DemandContext(**demand_ctx),
        cost_estimate=estimate_cost(engine, priority, engine_cfg),
        maintenance_forecast=forecast_maintenance(engine, engine_cfg, fleet_cfg),
        assessed_at=datetime.now(UTC),
    )
