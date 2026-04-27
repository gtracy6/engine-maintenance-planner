from fastapi import APIRouter, HTTPException

from app.core.engine_config import EngineTypeConfig, ScenarioConfig
from app.core.loader import get_engine_type, get_scenario, list_engine_types, list_scenarios

router = APIRouter(prefix="/config", tags=["Configuration"])


@router.get("/engine-types")
def list_available_engine_types() -> dict:
    """List all available engine type configurations."""
    return {"engine_types": list_engine_types()}


@router.get("/engine-types/{name}", response_model=EngineTypeConfig)
def get_engine_type_config(name: str) -> EngineTypeConfig:
    """Return the full configuration for a named engine type."""
    try:
        return get_engine_type(name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/scenarios")
def list_available_scenarios() -> dict:
    """List all available fleet scenario configurations."""
    return {"scenarios": list_scenarios()}


@router.get("/scenarios/{name}", response_model=ScenarioConfig)
def get_scenario_config(name: str) -> ScenarioConfig:
    """Return the full configuration for a named fleet scenario."""
    try:
        return get_scenario(name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
