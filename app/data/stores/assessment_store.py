"""
In-memory store
"""

from collections import defaultdict

from app.schemas.assessment import AssessmentResult

_history: dict[str, list[AssessmentResult]] = defaultdict(list)


def save(result: AssessmentResult) -> None:
    _history[result.engine_id].append(result)


def get_engine_history(engine_id: str) -> list[AssessmentResult]:
    return _history.get(engine_id, [])


def get_all_history() -> list[AssessmentResult]:
    records = [r for records in _history.values() for r in records]
    return sorted(records, key=lambda r: r.assessed_at, reverse=True)


def get_latest(engine_id: str) -> AssessmentResult | None:
    records = _history.get(engine_id)
    return records[-1] if records else None
