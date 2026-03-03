from __future__ import annotations

import logging
import httpx


logger = logging.getLogger(__name__)


class AiClient:
    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model

        self._timeout = httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0)

    async def ask(self, user_text: str) -> str:
        url = f"{self._base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": "Ты полезный ассистент. Отвечай кратко и по делу, на русском."},
                {"role": "user", "content": user_text},
            ],
            "temperature": 0.3,
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            r = await client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()

        try:
            return (data["choices"][0]["message"]["content"] or "").strip()
        except Exception:
            logger.exception("Unexpected AI response shape: %s", data)
            return "Не смог разобрать ответ модели. Попробуй ещё раз."
