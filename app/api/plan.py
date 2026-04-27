from fastapi import APIRouter

from app.domain.planner import run_simulation
from app.schemas.plan import PoolPlanInput, TwelveMonthPlan

router = APIRouter(prefix="/plan", tags=["Planning"])


@router.post("/simulate", response_model=TwelveMonthPlan)
def simulate_pool_plan(plan_input: PoolPlanInput):
    """
    Run a 12-month supply/demand simulation across the engine pool.
    Returns engine timelines, per-fleet monthly balances, deficit alerts,
    optimised fleet reassignments, and recommendations.
    """
    return run_simulation(plan_input)


@router.post("/simulate/summary")
def simulate_pool_summary(plan_input: PoolPlanInput):
    """
    Lightweight simulation — returns only summary, alerts, and recommendations.
    Useful for dashboards that don't need full per-engine timelines.
    """
    plan = run_simulation(plan_input)
    return {
        "summary": plan.summary,
        "deficit_alerts": plan.deficit_alerts,
        "recommendations": plan.recommendations,
    }
