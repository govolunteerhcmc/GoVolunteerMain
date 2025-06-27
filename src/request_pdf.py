from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from src.sheets_utils import update_pdf_requested

router = APIRouter()

class PDFRequest(BaseModel):
    fullName: str
    citizenId: str
    email: str

@router.post("/request-pdf")
def request_pdf(data: PDFRequest):
    updated = update_pdf_requested(data.fullName, data.citizenId, data.email)
    if not updated:
        raise HTTPException(status_code=404, detail="Không tìm thấy bản ghi để cập nhật.")
    return {"message": "Yêu cầu gửi chứng chỉ qua email đã được ghi nhận."}
