from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from src.sheets_utils import find_activity_info

router = APIRouter()

class LookupRequest(BaseModel):
    fullName: str
    citizenId: str

@router.post("/find-activities")
def find_activities(request: LookupRequest):
    activity = find_activity_info(request.fullName, request.citizenId)
    if not activity:
        raise HTTPException(status_code=404, detail="Không tìm thấy hoạt động.")
    return {"activities": [activity]}
