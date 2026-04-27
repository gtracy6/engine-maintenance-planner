from pydantic import BaseModel

from app.schemas.assessment import AssessmentResult
from app.schemas.engine import EngineInput


class FleetInput(BaseModel):
    engines: list[EngineInput]


class FleetSummary(BaseModel):
    total_engines: int
    high_priority: int
    medium_priority: int
    low_priority: int
    assessments: list[AssessmentResult]
