from fastapi import APIRouter, HTTPException

from app.core.loader import get_scenario
from app.data.stores import assessment_store as storage
from app.domain.assessment import evaluate_engine
from app.schemas.assessment import AssessmentResponse
from app.schemas.engine import EngineInput
from app.schemas.fleet import FleetInput, FleetSummary
from app.services.explanation import generate_llm_explanation, generate_mock_explanation

router = APIRouter(prefix="/assess", tags=["Assessment"])


def _validate_fleet(engine: EngineInput) -> None:
    """Raise 422 if the engine's fleet is not defined in its scenario."""
    try:
        scenario = get_scenario(engine.scenario)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    if engine.fleet not in scenario.fleets:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Fleet '{engine.fleet}' not in scenario '{engine.scenario}'. "
                f"Available: {list(scenario.fleets)}"
            ),
        )


def _run_assessment(engine: EngineInput) -> AssessmentResponse:
    _validate_fleet(engine)
    engine_dict = engine.model_dump()
    decision = evaluate_engine(engine)
    storage.save(decision)

    try:
        explanation = generate_llm_explanation(engine_dict, decision.model_dump())
        explanation_source = "llm"
    except Exception as e:
        explanation = generate_mock_explanation(engine_dict, decision.model_dump())
        explanation_source = f"mock_fallback: {e}"

    return AssessmentResponse(
        engine_id=engine.engine_id,
        decision=decision,
        explanation=explanation,
        explanation_source=explanation_source,
    )


@router.post("", response_model=AssessmentResponse)
def assess_engine(engine: EngineInput):
    """Assess a single engine and return recommendation + explanation."""
    return _run_assessment(engine)


@router.post("/fleet", response_model=FleetSummary)
def assess_fleet(fleet: FleetInput):
    """Assess all engines in a fleet batch; returns results sorted by urgency."""
    for engine in fleet.engines:
        _validate_fleet(engine)

    assessments = sorted(
        [evaluate_engine(e) for e in fleet.engines],
        key=lambda a: a.score,
        reverse=True,
    )
    for a in assessments:
        storage.save(a)

    return FleetSummary(
        total_engines=len(assessments),
        high_priority=sum(1 for a in assessments if a.priority == "high"),
        medium_priority=sum(1 for a in assessments if a.priority == "medium"),
        low_priority=sum(1 for a in assessments if a.priority == "low"),
        assessments=assessments,
    )
