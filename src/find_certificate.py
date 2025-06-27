from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from src.sheets_utils import find_certificate_info

router = APIRouter()

class LookupRequest(BaseModel):
    fullName: str
    citizenId: str

@router.post("/find-certificates")
def find_certificates(request: LookupRequest):
    cert = find_certificate_info(request.fullName, request.citizenId)
    if not cert:
        raise HTTPException(status_code=404, detail="Không tìm thấy chứng nhận.")
    return {"certificates": [cert]}