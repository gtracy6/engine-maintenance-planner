from datetime import datetime

from pydantic import BaseModel


class CostEstimate(BaseModel):
    immediate_maintenance_cost: int  # USD
    delay_risk_cost: int  #estimated cost if action is delayed
    recommendation: str


class DemandContext(BaseModel):
    """
    Fleet demand profile
    """
    fleet: str
    current_month: str  
    current_month_demand: int
    next_month_demand: int
    demand_tier: str 
    upcoming_peak: bool
    maintenance_window: bool 
    monthly_schedule: dict 


class MaintenanceForecast(BaseModel):
    """
    maintenance forecast
    """
    fleet: str
    annual_utilisation_cycles: int
    remaining_cycles: int
    months_until_shop: float
    predicted_shop_date: datetime
    within_3_months: bool
    within_6_months: bool
    within_12_months: bool
    within_24_months: bool
    forecast_note: str


class AssessmentResult(BaseModel):
    engine_id: str
    fleet: str
    engine_type: str 
    scenario: str  
    utilisation_level: str 
    recommendation: str
    priority: str
    score: int
    drivers: list[str]
    demand_context: DemandContext
    cost_estimate: CostEstimate
    maintenance_forecast: MaintenanceForecast
    assessed_at: datetime


class AssessmentResponse(BaseModel):
    engine_id: str
    decision: AssessmentResult
    explanation: str
    explanation_source: str
