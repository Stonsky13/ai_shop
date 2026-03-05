from __future__ import annotations

import logging
from app.clients.ai_client import AiClient
from app.clients.sheets_client import SheetsClient


logger = logging.getLogger(__name__)

class AiFlow:
    def __init__(self, ai: AiClient, sheets: SheetsClient) -> None:
        self._ai = ai
        self._sheets = sheets

    async def ask_and_log(self, tg_id: int, username: str, question: str) -> str:
        self._sheets.log_event(tg_id, username, "ai_ask", {"q": question})
        try:
            ans = await self._ai.ask(question)
            self._sheets.log_event(tg_id, username, "ai_answer", {"len": len(ans)})
            return ans
        except Exception as e:
            logger.exception("AI request failed")
            self._sheets.log_event(tg_id, username, "ai_answer_error", {"error": str(e)})
            return "Ошибка при обращении к AI. Попробуй позже."
