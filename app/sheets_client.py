from __future__ import annotations

import json
import logging
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)


class SheetsClient:
    def __init__(self, service_account_json_path: str, spreadsheet_id: str, sheet_name: str) -> None:
        creds = Credentials.from_service_account_file(
            service_account_json_path,
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        self._gc = gspread.authorize(creds)
        self._sh = self._gc.open_by_key(spreadsheet_id)
        self._ws = self._sh.worksheet(sheet_name)

    def append_row(self, row: list[str]) -> None:
        self._ws.append_row(row, value_input_option="RAW")

    def log_event(self, tg_id: int, username: str, event: str, payload: dict) -> None:
        ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        row = [ts, str(tg_id), username or "", event, json.dumps(payload, ensure_ascii=False)]
        try:
            self.append_row(row)
        except Exception:
            logger.exception("Failed to log event to Google Sheets")
