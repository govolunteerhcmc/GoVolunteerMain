import os
import time
from typing import List, Dict, Any

from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# --- SCRAPER MODULE ---
from scraper import scrape_news as fetch_news_from_source
from scraper import scrape_article_with_requests as fetch_article_from_source
from scraper import (
    scrape_chuong_trinh_chien_dich_du_an,
    scrape_skills,
    scrape_ideas,
    scrape_clubs,
    BASE_URL,
)

# --- ROUTER MODULES ---
from src.find_activities import router as activities_router
from src.find_certificate import router as certificates_router
from src.request_pdf import router as pdf_router

# ==========================================================================
# --- 1. INIT APP & CORS ---
# ==========================================================================
app = FastAPI(
    title="GoVolunteer API (Scraper & Lookup)",
    description="API hợp nhất cho cả scrape và tra cứu từ Google Sheets",
    version="9.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ==========================================================================
# --- 2. GOOGLE SHEETS SETUP ---
# ==========================================================================
SERVICE_ACCOUNT_FILE = 'credentials.json'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
ACTIVITY_SHEET_ID = '1BGbTI34I8H_cZaRey5UHuPkxZa1bMsk1JanXCZFdj3s'
CERTIFICATE_SHEET_ID = '1uAVk9XZExLgCdfukYGxk8NSFh5CZtrfjS0gQtxjTQaQ'
SHEET_NAME = 'Sheet1'

sheet_api = None

@app.on_event("startup")
def startup_event():
    global sheet_api
    print("🔧 Khởi tạo Google Sheets API...")
    try:
        if os.path.exists(SERVICE_ACCOUNT_FILE):
            creds = service_account.Credentials.from_service_account_file(
                SERVICE_ACCOUNT_FILE, scopes=SCOPES)
            service = build('sheets', 'v4', credentials=creds)
            sheet_api = service.spreadsheets()
            print("✅ Kết nối Google Sheets thành công.")
        else:
            print(f"❌ Không tìm thấy file: {SERVICE_ACCOUNT_FILE}")
    except Exception as e:
        print(f"❌ Lỗi khi khởi tạo Google Sheets API: {e}")

# ==========================================================================
# --- 3. SCRAPER ENDPOINTS ---
# ==========================================================================
cache = {"news_data": None, "last_fetched": 0}
CACHE_DURATION_SECONDS = 1800  # 30 phút

@app.get("/")
def read_root():
    return {"status": "online", "message": "API GoVolunteer hoạt động"}

@app.get("/news")
def get_all_news():
    current_time = time.time()
    if cache["news_data"] and (current_time - cache["last_fetched"] < CACHE_DURATION_SECONDS):
        return cache["news_data"]
    data = fetch_news_from_source()
    if not data:
        raise HTTPException(status_code=503, detail="Không thể lấy dữ liệu tin tức.")
    cache["news_data"] = data
    cache["last_fetched"] = current_time
    return data

@app.get("/clubs")
def get_clubs():
    data = scrape_clubs()
    if not data:
        raise HTTPException(status_code=503, detail="Không thể lấy dữ liệu CLB.")
    return data

@app.get("/chuong-trinh-chien-dich-du-an")
def get_campaigns():
    data = scrape_chuong_trinh_chien_dich_du_an()
    if not data:
        raise HTTPException(status_code=503, detail="Không thể lấy dữ liệu chương trình.")
    return data

@app.get("/skills")
def get_skills():
    data = scrape_skills()
    if not data:
        raise HTTPException(status_code=503, detail="Không thể lấy dữ liệu kỹ năng.")
    return data

@app.get("/ideas")
def get_ideas():
    data = scrape_ideas()
    if not data:
        raise HTTPException(status_code=503, detail="Không thể lấy dữ liệu ý tưởng.")
    return data

@app.get("/article")
def get_article_detail(url: str):
    if not url or not url.startswith(BASE_URL):
        raise HTTPException(status_code=400, detail=f"URL phải bắt đầu bằng {BASE_URL}")
    content = fetch_article_from_source(url)
    if content is None:
        raise HTTPException(status_code=503, detail="Không thể lấy nội dung bài viết.")
    return {"html_content": content}

# ==========================================================================
# --- 4. ADMIN TOOLS: XEM TOÀN BỘ DỮ LIỆU ---
# ==========================================================================
def _get_all_sheet_data(spreadsheet_id: str) -> Dict[str, Any]:
    if not sheet_api:
        raise HTTPException(status_code=503, detail="Google Sheets API không khả dụng.")
    try:
        result = sheet_api.values().get(spreadsheetId=spreadsheet_id, range=SHEET_NAME).execute()
        values = result.get("values", [])
        if not values or len(values) < 2:
            return {"count": 0, "headers": values[0] if values else [], "data": []}
        headers = values[0]
        records = [
            {headers[i]: (row[i] if i < len(row) else "") for i in range(len(headers))}
            for row in values[1:]
        ]
        return {"count": len(records), "headers": headers, "data": records}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/all-data")
def get_all_data_for_auditing():
    activities = _get_all_sheet_data(ACTIVITY_SHEET_ID)
    certificates = _get_all_sheet_data(CERTIFICATE_SHEET_ID)
    return {
        "activities": activities,
        "certificates": certificates
    }

# ==========================================================================
# --- 5. INCLUDE ROUTERS (TÁCH MODULE) ---
# ==========================================================================
app.include_router(activities_router)
app.include_router(certificates_router)
app.include_router(pdf_router)
