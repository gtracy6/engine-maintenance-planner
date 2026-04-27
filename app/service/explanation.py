import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

_client = OpenAI(api_key=os.getenv("AI_API_KEY")) #use openai by dufault
_model = os.getenv("AI_MODEL", "gpt-4.1-mini")


def _build_prompt(engine_input: dict, decision: dict) -> str:
    cost = decision.get("cost_estimate", {})
    forecast = decision.get("maintenance_forecast", {})
    demand = decision.get("demand_context", {})

    return f"""
You are an asset decision support assistant for airline engine management.

Engine data:
- Engine ID: {engine_input['engine_id']}
- Fleet: {engine_input['fleet']}
- Cycles since shop: {engine_input['cycles_since_shop']} / 20,000 max
- Remaining useful life: {engine_input['remaining_useful_life']}
- Condition score: {engine_input['condition_score']}
- Lease return due: {engine_input['lease_return_due']}
- Spare available: {engine_input['spare_available']}

Decision result:
- Recommendation: {decision['recommendation']}
- Priority: {decision['priority']}
- Score: {decision['score']}
- Drivers: {', '.join(decision['drivers']) if decision['drivers'] else 'none'}
- Estimated maintenance cost: USD {cost.get('immediate_maintenance_cost', 'N/A'):,}
- Estimated delay risk cost: USD {cost.get('delay_risk_cost', 'N/A'):,}

Demand context (fleet {engine_input.get('fleet', '')}):
- This month demand: {demand.get('current_month_demand', 'N/A')} engines
- Next month demand: {demand.get('next_month_demand', 'N/A')} engines
- Demand tier: {demand.get('demand_tier', 'N/A')}
- Upcoming peak: {demand.get('upcoming_peak', 'N/A')}
- Maintenance window: {demand.get('maintenance_window', 'N/A')}

Maintenance forecast:
- Fleet utilisation: {forecast.get('annual_utilisation_cycles', 'N/A')} cycles/year
- Remaining cycles: {forecast.get('remaining_cycles', 'N/A'):,}
- Months until shop: {forecast.get('months_until_shop', 'N/A')}
- Predicted shop date: {forecast.get('predicted_shop_date', 'N/A')}

Write a concise business-friendly explanation (max 160 words) covering:
1. Recommendation summary (1-2 sentences)
2. Main decision drivers
3. Shop visit timeline and financial risk if action is delayed

Use clear operational language suitable for a capex review meeting.
Do not invent data.
""".strip()


def generate_llm_explanation(engine_input: dict, decision: dict) -> str:
    prompt = _build_prompt(engine_input, decision)
    response = _client.responses.create(
        model=_model,
        input=[
            {
                "role": "system",
                "content": "You explain structured asset maintenance recommendations clearly for business stakeholders.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.2, # use 0.2 for more stable output
    )
    return response.output_text.strip()


def generate_mock_explanation(engine_input: dict, decision: dict) -> str:
    cost = decision.get("cost_estimate", {})
    forecast = decision.get("maintenance_forecast", {})
    drivers = ", ".join(decision["drivers"]) or "the evaluated engine conditions"

    return (
        f"Recommendation: {decision['recommendation']} ({decision['priority']} priority). "
        f"Key drivers: {drivers}. "
        f"Estimated maintenance cost: USD {cost.get('immediate_maintenance_cost', 'N/A'):,}. "
        f"Shop visit projected in ~{forecast.get('months_until_shop', 'N/A')} months "
        f"({forecast.get('remaining_cycles', 'N/A'):,} cycles remaining). "
        f"Delaying action could cost up to USD {cost.get('delay_risk_cost', 'N/A'):,} in additional risk."
    )
