"""API pública: erro(), alerta(), info().

Comportamento (PLANO.md):
- erro:   sempre dispara Telegram + grava JSONL
- alerta: dispara Telegram + grava JSONL, com throttle de 5 min por chave
- info:   apenas grava JSONL (Telegram somente se MONITOR_NIVEL=info)

A lib nunca propaga exceção para o caller — todas as falhas são engolidas
para garantir que um problema de notificação não derrube o pipeline cliente.
"""

from __future__ import annotations

import socket
from datetime import datetime, timezone

from dotenv import load_dotenv

from . import config, drive_resolver, event_log, telegram_client, throttle

load_dotenv()

NIVEL_INFO = "info"
NIVEL_ALERTA = "alerta"
NIVEL_ERRO = "erro"

_PRIORIDADE_NIVEL = {NIVEL_INFO: 0, NIVEL_ALERTA: 1, NIVEL_ERRO: 2}
_THROTTLE_TTL_SEGUNDOS = 300

_LIMITE_TRACEBACK_CHARS = 1500


def _deve_enviar_telegram(nivel: str, nivel_minimo: str) -> bool:
    return _PRIORIDADE_NIVEL.get(nivel, 1) >= _PRIORIDADE_NIVEL.get(nivel_minimo, 1)


def _construir_evento(
    nivel: str,
    titulo: str,
    detalhes: str,
    traceback: str | None,
    contexto: dict | None,
    projeto: str,
) -> dict:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "projeto": projeto,
        "host": socket.gethostname(),
        "nivel": nivel,
        "titulo": titulo,
        "detalhes": detalhes or "",
        "traceback": traceback,
        "contexto": contexto or {},
    }


def _formatar_telegram(evento: dict) -> str:
    icone = {NIVEL_ERRO: "🚨", NIVEL_ALERTA: "⚠️", NIVEL_INFO: "ℹ️"}.get(
        evento["nivel"], "•"
    )
    linhas = [
        f"{icone} *{evento['nivel'].upper()}* — `{evento['projeto']}`",
        f"*{evento['titulo']}*",
    ]
    if evento.get("detalhes"):
        linhas += ["", evento["detalhes"]]
    if evento.get("contexto"):
        linhas.append("")
        for k, v in evento["contexto"].items():
            linhas.append(f"• `{k}`: {v}")
    if evento.get("traceback"):
        tb = evento["traceback"]
        if len(tb) > _LIMITE_TRACEBACK_CHARS:
            tb = "..." + tb[-_LIMITE_TRACEBACK_CHARS:]
        linhas += ["", "```", tb, "```"]
    linhas += ["", f"_{evento['host']} • {evento['timestamp']}_"]
    return "\n".join(linhas)


def _emitir(
    nivel: str,
    titulo: str,
    detalhes: str,
    traceback: str | None,
    contexto: dict | None,
    com_throttle: bool,
) -> None:
    try:
        cfg = config.obter()
        evento = _construir_evento(
            nivel, titulo, detalhes, traceback, contexto, cfg["projeto"]
        )

        # 1) Persistência JSONL (best-effort, sempre)
        try:
            event_log.append_event(cfg["drive_folder"], cfg["projeto"], evento)
        except Exception:
            pass

        # 2) Throttle (apenas para alerta)
        if com_throttle:
            chave = f"{nivel}:{cfg['projeto']}:{titulo}"
            if not throttle.deve_emitir(chave, _THROTTLE_TTL_SEGUNDOS):
                return

        # 3) Telegram (somente se o nível supera o mínimo configurado)
        if not _deve_enviar_telegram(nivel, cfg["nivel_minimo"]):
            return
        try:
            token = drive_resolver.resolver(cfg["tg_token_raw"])
            chat_id = drive_resolver.resolver(cfg["tg_chat_id_raw"])
            mensagem = _formatar_telegram(evento)
            telegram_client.send_text(token, chat_id, mensagem)
        except Exception:
            pass
    except Exception:
        # Última linha de defesa: lib jamais quebra o caller
        pass


def erro(
    titulo: str,
    detalhes: str = "",
    traceback: str | None = None,
    contexto: dict | None = None,
) -> None:
    """Notifica erro. Sempre dispara Telegram + grava JSONL."""
    _emitir(NIVEL_ERRO, titulo, detalhes, traceback, contexto, com_throttle=False)


def alerta(
    titulo: str,
    detalhes: str = "",
    contexto: dict | None = None,
) -> None:
    """Notifica alerta. Dispara Telegram + grava JSONL, com throttle de 5 min por chave."""
    _emitir(NIVEL_ALERTA, titulo, detalhes, None, contexto, com_throttle=True)


def info(
    titulo: str,
    detalhes: str = "",
    contexto: dict | None = None,
) -> None:
    """Registra info. Grava JSONL; só envia Telegram se MONITOR_NIVEL=info."""
    _emitir(NIVEL_INFO, titulo, detalhes, None, contexto, com_throttle=False)
