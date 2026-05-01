"""Cliente Telegram síncrono baseado em httpx.

Padrão replicado de automacoes/telegram_msg/bots/base.py (versão sync, sem dependência de async).
"""

from __future__ import annotations

import httpx

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
TIMEOUT_SEGUNDOS = 15.0
LIMITE_MENSAGEM = 4000


def send_text(
    token: str | None,
    chat_id: str | None,
    text: str,
    parse_mode: str = "Markdown",
) -> bool:
    """Envia mensagem ao Telegram. Retorna True em sucesso, False em qualquer falha (silenciosa)."""
    if not token or not chat_id or not text:
        return False

    chunks = _split_in_chunks(text, LIMITE_MENSAGEM)
    url = TELEGRAM_API.format(token=token)

    try:
        with httpx.Client(timeout=TIMEOUT_SEGUNDOS) as client:
            for chunk in chunks:
                payload = {
                    "chat_id": chat_id,
                    "text": chunk,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": True,
                }
                resp = client.post(url, json=payload)
                resp.raise_for_status()
        return True
    except Exception:
        return False


def _split_in_chunks(text: str, max_len: int) -> list[str]:
    """Divide texto em pedaços <= max_len, preferindo quebras de linha."""
    if len(text) <= max_len:
        return [text]

    chunks: list[str] = []
    restante = text
    while restante:
        if len(restante) <= max_len:
            chunks.append(restante)
            break
        corte = restante.rfind("\n", 0, max_len)
        if corte == -1 or corte == 0:
            corte = max_len
        chunks.append(restante[:corte])
        restante = restante[corte:].lstrip("\n")
    return chunks
