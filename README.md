# Engine Maintenance Decision Agent

> Personal side project built for experimentation. Does not reflect real airline operations or proprietary business logic — purely a conceptual demo.

---

## Why this project exists

Aircraft engine planning is a complex asset decision problem. Fleet planners need to balance engine health, shop visit timing, spare availability, utilisation, lease return constraints, and fleet demand.

This project demonstrates a simplified decision-support system that helps answer questions such as:

- Which engines are at highest maintenance risk?
- When could upcoming shop visits create fleet supply deficits?
- After maintenance, which fleet should a returned engine be assigned to?
- How can technical maintenance outputs be explained in a business-friendly way?


## What it does

The system provides four core capabilities:

1. Engine assessment  
   Scores individual engines based on lifecycle, condition, utilisation, spare availability, and lease return risk.

2. Fleet-level prioritisation  
   Assesses an engine pool and ranks engines by maintenance urgency.

3. 12-month Engine pool simulation  
   Simulates shop visit triggers, engine returns, fleet supply, demand, and deficit alerts month by month.

4. Reassignment recommendation  
   Uses a lookahead heuristic to assign returned engines to the fleet where they best support future demand.


## Architecture

**Layer responsibilities:**

| Layer | Path | Role |
|---|---|---|
| API | `app/api/` | HTTP routing only, no business logic |
| Domain | `app/domain/` | Pure business logic — scoring, simulation, forecasting |
| Services | `app/services/` | Application services — LLM explanation (external calls) |
| Data | `app/data/repositories/` | Demand data access |
| Data | `app/data/stores/` | In-memory assessment history |
| Schemas | `app/schemas/` | All Pydantic input/output models |
| Core | `app/core/` | Config constants and YAML loader |

## Important design choice

The LLM does not make the maintenance decision.

The decision logic is rule-based and transparent. The LLM is only used to convert the structured output into a clearer business explanation. If the API key is missing or unavailable, the system falls back to a rule-based explanation.

## Current limitations

This is a conceptual demo, not a production maintenance system.

Current demo limitations:

- Uses conceptualised and simplified maintenance rules and synthetic assumptions
- No persistent database yet
- Reassignment logic is a lookahead heuristic, not a full mathematical optimisation model
- No real airline operational data
- No safety-critical validation

---

## Inputs & Outputs

### Inputs

| Field | Description |
|-------|-------------|
| `engine_id` | Engine ID |
| `fleet` | Fleet |
| `cycles_since_shop` | Cycles since last maintenance |
| `remaining_useful_life` | Fraction of life remaining (0.0–1.0) |
| `utilisation_level` | Fleet utilisation — High (1,500 cy/yr) / Medium (1,000) / Low (500) |
| `condition_score` | Engine condition rating (0.0 = failed, 1.0 = perfect) |
| `lease_return_due` | Whether lease return deadline is approaching |
| `spare_available` | Whether a spare engine is available |

### Outputs

| Field | Description |
|-------|-------------|
| `recommendation` | `continue_operation` / `monitor_or_plan` / `send_to_maintenance` |
| `priority` | `low` / `medium` / `high` |
| `score` | Composite urgency score driving the recommendation |
| `drivers` | Key factors that contributed to the decision |
| `explanation` | Business-friendly narrative (LLM or rule-based fallback) |
| `cost_estimate` | Immediate maintenance cost and delay risk in USD |
| `maintenance_forecast` | Predicted shop visit date based on fleet utilisation |
| `demand_context` | Current and upcoming fleet demand gap |

---

## Features

- **Engine assessment** — simplified rule-based (can be updated with actual deterioration model, failure risk model)
- **Maintenance forecast** — predicts shop visit date based on fleet utilisation rate (or other deterioration model)
- **Cost estimation** — immediate maintenance cost vs delay risk in USD (simplified delay risk concept)
- **Fleet demand scheduling** — monthly engine demand per fleet/subfleet
- **12-month pool simulation** — simulates maintenance triggers, shop visits, and supply/demand balance across the entire pool
- **Optimised fleet reassignment** — when an engine exits maintenance, a lookahead algorithm assigns it to the fleet where it maximises total satisfied demand

---

## Project Structure

```
engine-maitenance-planner/
├── app/
│   ├── main.py                        
│   ├── api/                      
│   │   ├── assess.py                  
│   │   ├── demand.py              
│   │   ├── history.py                 
│   │   ├── plan.py                   
│   │   ├── sensitivity.py             
│   │   └── config_api.py              # GET
│   ├── domain/                        # business logic
│   │   ├── assessment.py              # evaluate_engine, forecast, cost
│   │   └── planner.py                 # 12-month simulation + optimiser
│   ├── services/                      
│   │   └── explanation.py             # LLM / mock explanation generator
│   ├── schemas/                      
│   │   ├── engine.py                  
│   │   ├── assessment.py             
│   │   ├── fleet.py                  
│   │   ├── plan.py                    
│   │   └── sensitivity.py             
│   ├── data/
│   │   ├── repositories/
│   │   │   └── fleet_demand.py        # Monthly demand
│   │   └── stores/
│   │       └── assessment_store.py    # In-memory assessment history
│   └── core/
│       ├── config.py                  # constants
│       ├── engine_config.py           # Pydantic config models
│       └── loader.py                  # YAML config loader
├── config/
│   ├── engine_types/              
│   │   ├── v2500.yaml
│   │   ├── leap.yaml
│   │   └── cfm56.yaml
│   └── scenarios/                     # scenario testing
│       ├── default.yaml
│       └── high_demand.yaml
└── tests/
    └── test_data.json                 
```

---

## Getting Started

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

Create `app/.env`:

```env
AI_API_KEY=sk-...
AI_MODEL=gpt-...
```

If the key is missing or quota is exceeded,  falls back to a rule-based mock explanation automatically.

### 3. Start the server

```bash
cd engine-optmiser-demo-v2
uvicorn app.main:app --reload
```
docs available at `http://localhost:8000/docs`

---

## API Reference

### Assessment

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/assess` | Assess a single engine |
| `POST` | `/assess/fleet` | Assess a batch of engines, sorted by urgency |

**Single engine request:**
```json
{
  "engine_id": "ABC-01",
  "fleet": "ABC",
  "cycles_since_shop": 15000,
  "remaining_useful_life": 0.18,
  "condition_score": 0.55,
  "lease_return_due": false,
  "spare_available": true
}
```

**Response includes:** recommendation, priority, score, drivers, cost estimate, maintenance forecast, demand context, and a business-friendly explanation.

---

### Demand

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/demand/{fleet}` | Demand context for current calendar month |
| `GET` | `/demand/{fleet}/{month}` | Engine demand for a specific month (1–12) |

---

### History

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/history` | All past assessments, newest first |
| `GET` | `/history/{engine_id}` | Assessment history for one engine |
| `GET` | `/history/{engine_id}/latest` | Most recent assessment for one engine |

---

### Pool Planning

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/plan/simulate` | Full 12-month simulation with timelines |
| `POST` | `/plan/simulate/summary` | Summary only (alerts + recommendations) |

**Request:**
```json
{
  "start_month": 4,
  "shop_visit_duration": 2,
  "engines": [
    {
      "engine_id": "ABC-01",
      "fleet": "ABC",
      "cycles_since_shop": 17800,
      "remaining_useful_life": 0.07,
      "condition_score": 0.28,
      "status": "operational"
    },
    {
      "engine_id": "BCA-03",
      "fleet": "BCA",
      "cycles_since_shop": 0,
      "remaining_useful_life": 1.0,
      "condition_score": 0.97,
      "status": "in_maintenance",
      "months_remaining_in_shop": 2
    }
  ]
}
```

**Response includes:**
- `engine_timelines` — month-by-month status and fleet assignment per engine
- `fleet_balances` — supply vs demand per fleet per month
- `deficit_alerts` — months where supply falls short, with severity rating
- `fleet_reassignments` — engines reassigned to a different fleet after maintenance
- `recommendations` — plain-English planning actions

---

## Domain Configuration

All tuneable parameters are in `config/engine_types/*.yaml` and `config/scenarios/*.yaml`:

| Constant | Value | Description |
|----------|-------|-------------|
| `MAX_CYCLES_BETWEEN_SHOP` | 20,000 | Hard cycle limit before mandatory shop visit |
| `RUL_TRIGGER` | 0.10 | Send to shop when RUL ≤ 10% |
| `CYCLE_TRIGGER` | 18,000 | Send to shop when cycles ≥ 18,000 |
| `DEFAULT_SHOP_VISIT_DURATION` | 2 months | Default maintenance duration |
| `MAINTENANCE_BASE_COST` | $500,000 | Base shop visit cost (USD) |
| `MAINTENANCE_COST_PER_CYCLE` | $80 | Additional cost per cycle since last shop |

**Fleet utilisation (cycles/year):**

| Fleet | Cycles/year | Tier |
|-------|-------------|------|
| ABC | 1,500 | High |
| BCA | 1,000 | Medium |
| CBA | 500 | Low |

**Monthly engine demand:**

| Month | ABC | BCA | CBA |
|-------|-----|-----|-----|
| Jan | 8 | 3 | 1 |
| Feb | 8 | 3 | 1 |
| Mar | 9 | 4 | 2 |
| Apr | 10 | 4 | 2 |
| May | 11 | 5 | 2 |
| Jun | 12 | 6 | 3 |
| Jul | 12 | 6 | 3 |
| Aug | 11 | 5 | 3 |
| Sep | 10 | 4 | 2 |
| Oct | 9 | 4 | 2 |
| Nov | 7 | 3 | 1 |
| Dec | 6 | 4 | 2 |

---

## Simulation Logic

The planner runs month by month in the following order:

1. **Returns** — engines completing maintenance are returned to operational; the optimiser selects which fleet maximises remaining-month demand satisfaction
2. **Triggers** — operational engines hitting RUL ≤ 10% or cycles ≥ 18,000 are sent to the shop
3. **Supply count** — operational engines counted per fleet
4. **Utilisation** — cycles and RUL updated for all operational engines
5. **Snapshot** — engine status and fleet assignment recorded
6. **Balance** — supply vs demand recorded per fleet

**Fleet reassignment optimisation:** when an engine exits maintenance, the planner simulates the remaining months under each possible fleet assignment and picks the one with the highest total `min(supply, demand)` across all fleets and months.

---

## Test Data

A sample 12-engine pool is provided in `tests/test_data.json` covering all three fleets with a mix of operational and in-maintenance engines at varying lifecycle stages.

```bash
cd engine-agent
uvicorn app.main:app --reload &
curl -X POST http://localhost:8000/plan/simulate \
  -H "Content-Type: application/json" \
  -d @tests/test_data.json | python -m json.tool
```
