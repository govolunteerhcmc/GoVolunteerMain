import os
from typing import List, Dict, Any
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SERVICE_ACCOUNT_FILE = 'credentials.json'
ACTIVITY_SHEET_ID = '1BGbTI34I8H_cZaRey5UHuPkxZa1bMsk1JanXCZFdj3s'
CERTIFICATE_SHEET_ID = '1uAVk9XZExLgCdfukYGxk8NSFh5CZtrfjS0gQtxjTQaQ'
SHEET_NAME = 'Sheet1'


def get_sheet_api(scopes: List[str]):
    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        raise FileNotFoundError(f"File '{SERVICE_ACCOUNT_FILE}' không tồn tại.")
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=scopes)
    service = build('sheets', 'v4', credentials=creds)
    return service.spreadsheets()


def _search_one_sheet(sheet_api, spreadsheet_id: str, citizen_id: str):
    try:
        result = sheet_api.values().get(spreadsheetId=spreadsheet_id, range=SHEET_NAME).execute()
        values = result.get('values', [])

        if not values or len(values) < 2:
            return None

        headers = values[0]
        cccd_index = headers.index('CCCD')

        for row in values[1:]:
            if len(row) > cccd_index:
                if row[cccd_index].strip() == citizen_id.strip():
                    return {headers[i]: (row[i] if i < len(row) else '') for i in range(len(headers))}

        return None
    except HttpError as e:
        return {"error": f"Không thể truy cập Google Sheet. Mã lỗi: {e.resp.status}"}
    except Exception as e:
        return {"error": "Lỗi máy chủ nội bộ khi xử lý sheet."}


def find_activity_info(citizen_id: str):
    sheet_api = get_sheet_api(['https://www.googleapis.com/auth/spreadsheets.readonly'])
    return _search_one_sheet(sheet_api, ACTIVITY_SHEET_ID, citizen_id)


def find_certificate_info(citizen_id: str):
    sheet_api = get_sheet_api(['https://www.googleapis.com/auth/spreadsheets.readonly'])
    return _search_one_sheet(sheet_api, CERTIFICATE_SHEET_ID, citizen_id)


def update_pdf_requested(citizen_id: str, email: str):
    sheet_api = get_sheet_api(['https://www.googleapis.com/auth/spreadsheets'])

    result = sheet_api.values().get(spreadsheetId=CERTIFICATE_SHEET_ID, range=SHEET_NAME).execute()
    values = result.get('values', [])

    if not values or len(values) < 2:
        return False

    headers = values[0]
    try:
        cccd_index = headers.index('CCCD')
        email_index = headers.index('Email')
        requested_col_letter = "G"  
    except ValueError:
        raise Exception("Thiếu cột 'CCCD' hoặc 'Email' trong sheet.")

    for i, row in enumerate(values[1:], start=2):
        if len(row) > cccd_index:
            if row[cccd_index].strip() == citizen_id.strip():
                email_cell = f"{SHEET_NAME}!{chr(65 + email_index)}{i}"
                sheet_api.values().update(
                    spreadsheetId=CERTIFICATE_SHEET_ID,
                    range=email_cell,
                    valueInputOption="USER_ENTERED",
                    body={"values": [[email]]}
                ).execute()

                sheet_api.values().update(
                    spreadsheetId=CERTIFICATE_SHEET_ID,
                    range=f"{SHEET_NAME}!{requested_col_letter}{i}",
                    valueInputOption="USER_ENTERED",
                    body={"values": [["TRUE"]]}
                ).execute()

                return True  

    return False  