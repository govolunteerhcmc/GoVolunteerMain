import os
import time
from typing import List, Dict, Any

# --- FASTAPI & LIÊN QUAN ---
from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# --- GOOGLE SHEETS & LIÊN QUAN ---
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# --- MODULES SCRAPER (giữ nguyên) ---
from scraper import scrape_news as fetch_news_from_source
from scraper import scrape_article_with_requests as fetch_article_from_source
from scraper import (
    scrape_chuong_trinh_chien_dich_du_an,
    scrape_skills,
    scrape_ideas,
    scrape_clubs,
    BASE_URL
)

# ==========================================================================
# --- 1. KHỞI TẠO ỨNG DỤNG VÀ CẤU HÌNH ---
# ==========================================================================

app = FastAPI(
    title="GoVolunteer API (Scraper & Lookup)",
    description="API hợp nhất cho cả việc lấy dữ liệu từ trang web và tra cứu thông tin từ Google Sheets. Bổ sung endpoint /all-data để kiểm tra.",
    version="9.1.0"  # Phiên bản có thêm chức năng kiểm tra
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# --- CẤU HÌNH CHO GOOGLE SHEETS ---
SERVICE_ACCOUNT_FILE = 'credentials.json'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
ACTIVITY_SHEET_ID = '1BCJbZqR98jjjqCJq1B2I5p_GuyGi6xwmgxKsRhvxdh0'
CERTIFICATE_SHEET_ID = '17wUDyxg3QyaEwcVyT2bRuhvaVk5IqS40HmZMpSFYY6s'
SHEET_NAME = 'Sheet1'

# --- HỆ THỐNG CACHE CHO SCRAPER (giữ nguyên) ---
cache = {"news_data": None, "last_fetched": 0}
CACHE_DURATION_SECONDS = 1800  # 30 phút

# ==========================================================================
# --- 2. KHỞI TẠO DỊCH VỤ GOOGLE KHI APP START ---
# ==========================================================================

sheet_api = None

@app.on_event("startup")
def startup_event():
    """
    Khởi tạo kết nối tới Google Sheets API một lần duy nhất khi ứng dụng bắt đầu.
    """
    global sheet_api
    print("Bắt đầu khởi tạo dịch vụ Google Sheets...")
    try:
        if os.path.exists(SERVICE_ACCOUNT_FILE):
            creds = service_account.Credentials.from_service_account_file(
                SERVICE_ACCOUNT_FILE, scopes=SCOPES)
            service = build('sheets', 'v4', credentials=creds)
            sheet_api = service.spreadsheets()
            print(">>> Khởi tạo dịch vụ Google Sheets THÀNH CÔNG.")
        else:
            print(f"!!! LỖI QUAN TRỌNG: File credentials '{SERVICE_ACCOUNT_FILE}' không được tìm thấy.")
    except Exception as e:
        print(f"!!! LỖI KHỞI TẠO DỊCH VỤ GOOGLE: {e}")

# ==========================================================================
# --- 3. CÁC ENDPOINTS SCRAPER (KHÔNG THAY ĐỔI) ---
# ==========================================================================

@app.get("/", summary="Kiểm tra trạng thái API")
def read_root():
    return {"status": "online", "message": "API GoVolunteer (Phiên bản hợp nhất) đã sẵn sàng!"}

@app.get("/news", summary="Lấy danh sách tất cả tin tức")
def get_all_news():
    current_time = time.time()
    if cache["news_data"] and (current_time - cache["last_fetched"] < CACHE_DURATION_SECONDS):
        print("✅ Trả về dữ liệu /news từ cache.")
        return cache["news_data"]
    print("♻️ Cache /news hết hạn. Bắt đầu scrape dữ liệu mới...")
    data = fetch_news_from_source()
    if not data:
        raise HTTPException(status_code=503, detail="Không thể lấy dữ liệu từ trang chủ GoVolunteer.")
    cache["news_data"] = data
    cache["last_fetched"] = current_time
    print("💾 Đã cập nhật cache /news.")
    return data

@app.get("/clubs", summary="Lấy danh sách các CLB, Đội, Nhóm")
def get_clubs():
    data = scrape_clubs()
    if not data:
        raise HTTPException(status_code=503, detail="Không thể lấy dữ liệu CLB.")
    return data

@app.get("/chuong-trinh-chien-dich-du-an", summary="Lấy danh sách các chương trình, chiến dịch, dự án")
def get_campaigns():
    data = scrape_chuong_trinh_chien_dich_du_an()
    if not data:
        raise HTTPException(status_code=503, detail="Không thể lấy dữ liệu chương trình, chiến dịch, dự án.")
    return data

@app.get("/skills", summary="Lấy danh sách các bài viết kỹ năng")
def get_skills():
    data = scrape_skills()
    if not data:
        raise HTTPException(status_code=503, detail="Không thể lấy dữ liệu kỹ năng.")
    return data

@app.get("/ideas", summary="Lấy danh sách các ý tưởng tình nguyện")
def get_ideas():
    data = scrape_ideas()
    if not data:
        raise HTTPException(status_code=503, detail="Không thể lấy dữ liệu ý tưởng.")
    return data

@app.get("/article", summary="Lấy nội dung chi tiết của một bài viết")
def get_article_detail(url: str):
    if not url or not url.startswith(BASE_URL):
        raise HTTPException(status_code=400, detail=f"URL không hợp lệ. Phải bắt đầu bằng {BASE_URL}")
    content = fetch_article_from_source(url)
    if content is None:
        raise HTTPException(status_code=503, detail="Không thể lấy nội dung bài viết.")
    return {"html_content": content}

# ==========================================================================
# --- 4. LOGIC TRA CỨU & TRUY XUẤT GOOGLE SHEETS ---
# ==========================================================================

def search_all_records_in_sheet(spreadsheet_id: str, full_name: str, citizen_id: str) -> List[Dict[str, Any]]:
    """
    Hàm logic để tìm kiếm TẤT CẢ các dòng khớp với Họ tên và CCCD trong một sheet.
    """
    if not sheet_api:
        raise HTTPException(status_code=503, detail="Dịch vụ Google Sheets hiện không khả dụng.")
    try:
        result = sheet_api.values().get(spreadsheetId=spreadsheet_id, range=SHEET_NAME).execute()
        values = result.get('values', [])
        if not values or len(values) < 2: return []

        headers = values[0]
        try:
            # Đảm bảo các cột cần thiết cho việc tìm kiếm tồn tại
            name_index, cccd_index = headers.index('User_Name'), headers.index('CCCD')
        except ValueError:
            raise HTTPException(status_code=500, detail=f"Lỗi cấu trúc bảng tính (thiếu cột User_Name hoặc CCCD).")

        found_rows = []
        search_name_lower, search_citizen_id = full_name.strip().lower(), citizen_id.strip()

        for row in values[1:]:
            if len(row) > max(name_index, cccd_index):
                user_name_in_sheet = row[name_index].strip().lower()
                cccd_in_sheet = row[cccd_index].strip()
                if user_name_in_sheet == search_name_lower and cccd_in_sheet == search_citizen_id:
                    # Chuyển đổi dòng thành dict
                    found_rows.append({headers[i]: (row[i] if i < len(row) else '') for i in range(len(headers))})
        return found_rows
    except HttpError as http_error:
        raise HTTPException(status_code=http_error.resp.status, detail="Lỗi khi giao tiếp với Google Sheets.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi máy chủ nội bộ không xác định: {e}")

# --- [CHỨC NĂNG MỚI] HÀM LẤY TOÀN BỘ DỮ LIỆU ---
def _get_all_sheet_data(spreadsheet_id: str) -> Dict[str, Any]:
    """
    Hàm logic mới để lấy TOÀN BỘ dữ liệu từ một sheet.
    Dùng cho mục đích kiểm tra, không dùng cho tra cứu thông thường.
    """
    if not sheet_api:
        raise HTTPException(status_code=503, detail="Dịch vụ Google Sheets hiện không khả dụng.")
    try:
        result = sheet_api.values().get(spreadsheetId=spreadsheet_id, range=SHEET_NAME).execute()
        values = result.get('values', [])
        
        if not values or len(values) < 2:
            return {"count": 0, "headers": values[0] if values else [], "data": []}

        headers = values[0]
        data_rows = values[1:]
        
        # Chuyển đổi tất cả các dòng thành danh sách các dictionary
        all_records = [
            {headers[i]: (row[i] if i < len(row) else '') for i in range(len(headers))}
            for row in data_rows
        ]
        
        return {
            "count": len(all_records),
            "headers": headers,
            "data": all_records
        }
    except HttpError as http_error:
        raise HTTPException(status_code=http_error.resp.status, detail=f"Lỗi khi đọc sheet ID {spreadsheet_id}: {http_error.reason}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi máy chủ nội bộ khi xử lý sheet ID {spreadsheet_id}: {e}")


# ==========================================================================
# --- 5. ENDPOINT TRA CỨU (KHÔNG THAY ĐỔI) ---
# ==========================================================================

class LookupRequest(BaseModel):
    fullName: str = Field(..., example="Nguyễn Văn A")
    citizenId: str = Field(..., example="123456789")

@app.post("/lookup", summary="Tra cứu Tình nguyện viên từ Google Sheets")
def lookup_volunteer(request: LookupRequest):
    """
    Endpoint tra cứu thông tin tình nguyện viên. Logic này được giữ nguyên
    để đảm bảo tương thích với client hiện tại.
    """
    activity_list = search_all_records_in_sheet(ACTIVITY_SHEET_ID, request.fullName, request.citizenId)
    certificate_list = search_all_records_in_sheet(CERTIFICATE_SHEET_ID, request.fullName, request.citizenId)

    if not activity_list and not certificate_list:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy thông tin tình nguyện viên phù hợp. Vui lòng kiểm tra lại Họ tên và CCCD."
        )

    # Trả về "Đáp ứng kép" để đảm bảo an toàn cho cả client cũ và mới
    return {
        "activities": activity_list,
        "certificates": certificate_list,
        "activity": activity_list[0] if activity_list else None,
        "certificate": certificate_list[0] if certificate_list else None,
    }

# ==========================================================================
# --- 6. [CHỨC NĂNG MỚI] ENDPOINT KIỂM TRA & QUẢN TRỊ ---
# ==========================================================================

@app.get("/all-data", summary="[Kiểm tra] Lấy TOÀN BỘ dữ liệu từ 2 Google Sheets")
def get_all_data_for_auditing():
    """
    **Chức năng dành cho quản trị viên.**
    
    Endpoint này sẽ tải và trả về tất cả các bản ghi từ cả hai sheet
    'Hoạt động' và 'Chứng nhận'. Mục đích là để kiểm tra và xác thực
    toàn bộ dữ liệu, đảm bảo API đang đọc chính xác và đầy đủ.
    
    **Cảnh báo**: Việc này có thể tốn thời gian và tài nguyên nếu sheet có nhiều dữ liệu.
    """
    print("🔎 Bắt đầu yêu cầu lấy toàn bộ dữ liệu để kiểm tra...")
    
    # Lấy dữ liệu từ cả hai sheet bằng hàm logic mới
    activities_data = _get_all_sheet_data(ACTIVITY_SHEET_ID)
    certificates_data = _get_all_sheet_data(CERTIFICATE_SHEET_ID)
    
    print(f"✅ Lấy dữ liệu hoàn tất. {activities_data['count']} hoạt động, {certificates_data['count']} chứng nhận.")

    return {
        "message": "Dữ liệu đầy đủ từ hai sheet chỉ dành cho mục đích kiểm tra.",
        "activities": activities_data,
        "certificates": certificates_data
    }