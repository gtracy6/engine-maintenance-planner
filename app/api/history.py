from fastapi import APIRouter, HTTPException

from app.data.stores import assessment_store as storage

router = APIRouter(prefix="/history", tags=["History"])


@router.get("")
def get_all_history():
    """Return all assessment records, newest first."""
    records = storage.get_all_history()
    return {"total": len(records), "records": records}


@router.get("/{engine_id}")
def get_engine_history(engine_id: str):
    """Return assessment history for a specific engine."""
    records = storage.get_engine_history(engine_id)
    if not records:
        raise HTTPException(status_code=404, detail=f"No history found for engine '{engine_id}'")
    return {"engine_id": engine_id, "total": len(records), "records": records}


@router.get("/{engine_id}/latest")
def get_latest_assessment(engine_id: str):
    """Return the most recent assessment for a specific engine."""
    record = storage.get_latest(engine_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"No history found for engine '{engine_id}'")
    return record
