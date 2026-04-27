from fastapi import APIRouter, HTTPException

from app.core.loader import get_engine_type, get_scenario
from app.domain.assessment import evaluate_engine
from app.schemas.sensitivity import SensitivityPoint, SensitivityRequest, SensitivityResponse

router = APIRouter(prefix="/sensitivity", tags=["Sensitivity Analysis"])


@router.post("", response_model=SensitivityResponse)
def run_sensitivity(request: SensitivityRequest) -> SensitivityResponse:
    """
    Sweep a single EngineTypeConfig parameter across a list of values and
    return how the assessment outcome (priority, score, cost) changes at each point.

    Useful for:
    - Testing how sensitive the recommendation is to RUL or cycle thresholds
    - Comparing cost exposure under different cost-per-cycle assumptions
    - Finding the break-even value of a threshold parameter
    """
    try:
        engine_cfg = get_engine_type(request.engine.engine_type)
        scenario = get_scenario(request.engine.scenario)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    if request.engine.fleet not in scenario.fleets:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Fleet '{request.engine.fleet}' not in scenario '{request.engine.scenario}'. "
                f"Available: {list(scenario.fleets)}"
            ),
        )

    field = request.sweep.field
    baseline_value = float(getattr(engine_cfg, field))

    results: list[SensitivityPoint] = []
    for value in request.sweep.values:
        modified_cfg = engine_cfg.model_copy(
            update={field: type(getattr(engine_cfg, field))(value)}
        )
        result = evaluate_engine(request.engine, modified_cfg, scenario)
        results.append(
            SensitivityPoint(
                value=value,
                priority=result.priority,
                score=result.score,
                recommendation=result.recommendation,
                drivers=result.drivers,
                immediate_cost=result.cost_estimate.immediate_maintenance_cost,
                delay_risk_cost=result.cost_estimate.delay_risk_cost,
            )
        )

    return SensitivityResponse(
        engine_id=request.engine.engine_id,
        engine_type=engine_cfg.name,
        scenario=scenario.name,
        parameter=field,
        baseline_value=baseline_value,
        results=results,
    )
