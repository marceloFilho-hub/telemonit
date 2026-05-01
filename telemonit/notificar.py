"""API pública: erro(), alerta(), info().

Comportamento:
- erro:   sempre dispara Telegram + grava JSONL
- alerta: dispara Telegram + grava JSONL, com throttle de 5 min por chave
- info:   apenas grava JSONL (Telegram somente se MONITOR_NIVEL=info)

A lib nunca propaga exceção para o caller — todas as falhas são engolidas
para garantir que um problema de notificação não derrube o pipeline cliente.
"""

from __future__ import annotations

import socket
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from . import config, drive_resolver, event_log, telegram_client, throttle

load_dotenv()

# Log local de fallback: quando _emitir engolir uma exceção interna,
# grava uma linha aqui para que falhas silenciosas deixem rastro.
_FALLBACK_LOG_PATH = Path(tempfile.gettempdir()) / "telemonit_fallback.log"


def _registrar_fallback(motivo: str, contexto: dict | None = None) -> None:
    """Grava linha em log de fallback para diagnóstico de falhas internas."""
    try:
        linha = f"{datetime.now(timezone.utc).isoformat()} | {motivo}"
        if contexto:
            linha += f" | {contexto}"
        with _FALLBACK_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(linha + "\n")
    except Exception:
        pass

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
    run_id: str | None,
) -> dict:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "projeto": projeto,
        "run_id": run_id,
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
    cabecalho = f"{icone} *{evento['nivel'].upper()}* — `{evento['projeto']}`"
    if evento.get("run_id"):
        cabecalho += f" • run `{evento['run_id']}`"
    linhas = [cabecalho, f"*{evento['titulo']}*"]
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
    run_id: str | None,
    com_throttle: bool,
) -> None:
    try:
        cfg = config.obter()
        evento = _construir_evento(
            nivel, titulo, detalhes, traceback, contexto, cfg["projeto"], run_id
        )

        # 1) Persistência JSONL (best-effort, sempre — com fallback local)
        try:
            event_log.append_event(cfg["drive_folder"], cfg["projeto"], evento)
        except Exception as exc:
            _registrar_fallback(
                f"event_log falhou: {type(exc).__name__}: {exc}",
                {"nivel": nivel, "titulo": titulo, "projeto": cfg.get("projeto")},
            )

        # 2) Throttle (apenas para alerta) — chave inclui run_id quando presente
        if com_throttle:
            sufixo_run = f":{run_id}" if run_id else ""
            chave = f"{nivel}:{cfg['projeto']}{sufixo_run}:{titulo}"
            if not throttle.deve_emitir(chave, _THROTTLE_TTL_SEGUNDOS):
                return

        # 3) Telegram (somente se o nível supera o mínimo configurado)
        if not _deve_enviar_telegram(nivel, cfg["nivel_minimo"]):
            return
        try:
            token = drive_resolver.resolver(cfg["tg_token_raw"])
            chat_id = drive_resolver.resolver(cfg["tg_chat_id_raw"])
            mensagem = _formatar_telegram(evento)
            ok = telegram_client.send_text(token, chat_id, mensagem)
            if not ok:
                _registrar_fallback(
                    "telegram_client.send_text retornou False (resposta != 200, token/chat invalido ou rede)",
                    {"nivel": nivel, "titulo": titulo, "projeto": cfg.get("projeto")},
                )
        except Exception as exc:
            _registrar_fallback(
                f"telegram falhou: {type(exc).__name__}: {exc}",
                {"nivel": nivel, "titulo": titulo, "projeto": cfg.get("projeto")},
            )
    except Exception as exc:
        # Última linha de defesa: lib jamais quebra o caller, mas deixa rastro
        _registrar_fallback(
            f"_emitir engoliu exception: {type(exc).__name__}: {exc}",
            {"nivel": nivel, "titulo": titulo},
        )


def erro(
    titulo: str,
    detalhes: str = "",
    traceback: str | None = None,
    contexto: dict | None = None,
    run_id: str | None = None,
) -> None:
    """Notifica erro. Sempre dispara Telegram + grava JSONL."""
    _emitir(NIVEL_ERRO, titulo, detalhes, traceback, contexto, run_id, com_throttle=False)


def alerta(
    titulo: str,
    detalhes: str = "",
    contexto: dict | None = None,
    run_id: str | None = None,
) -> None:
    """Notifica alerta. Dispara Telegram + grava JSONL, com throttle de 5 min por chave."""
    _emitir(NIVEL_ALERTA, titulo, detalhes, None, contexto, run_id, com_throttle=True)


def info(
    titulo: str,
    detalhes: str = "",
    contexto: dict | None = None,
    run_id: str | None = None,
) -> None:
    """Registra info. Grava JSONL; só envia Telegram se MONITOR_NIVEL=info."""
    _emitir(NIVEL_INFO, titulo, detalhes, None, contexto, run_id, com_throttle=False)
