"""Bootstrap reusável de observabilidade — qualquer projeto Python.

Configura em uma única chamada:
- loguru: stdout colorido + arquivo `logs/<modulo>.log` com retenção 24h
  (default) e rotação por tamanho.
- telemonit.configurar(projeto=...) + telemonit.excepthook.instalar().
- sink customizado: `logger.warning()` -> `telemonit.alerta`,
  `logger.error()`/`logger.exception()` -> `telemonit.erro` automático.

Uso (no topo de qualquer entry point):

    from telemonit.observability import bootstrap
    logger = bootstrap(modulo="zendesk", projeto="dp_admissao")

    logger.info("processando")
    logger.warning("algo estranho")  # vai pra Donna automaticamente
    logger.error("falhou")           # vai pra Donna como erro
    raise RuntimeError("...")        # excepthook captura

Tolerâncias:
- Se `loguru` não estiver instalado, retorna logger fallback baseado em
  `print()` (compatível com a API). Recomendado: `pip install loguru>=0.7`.
- Se a SA do Drive falhar ou Telegram cair, `_emitir` registra em
  `tempfile.gettempdir()/telemonit_fallback.log` para deixar rastro.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from . import config as _config
from . import excepthook as _excepthook_mod
from . import notificar as _notificar


try:
    from loguru import logger as _loguru_logger
    _LOGURU_OK = True
except Exception:
    _loguru_logger = None  # type: ignore[assignment]
    _LOGURU_OK = False


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _resolver_logs_dir(logs_dir: Path | str | None) -> Path:
    """Resolve a pasta de logs. Default: <cwd>/logs. Fallback: tempdir."""
    if logs_dir is not None:
        candidato = Path(logs_dir)
    else:
        candidato = Path.cwd() / "logs"
    try:
        candidato.mkdir(parents=True, exist_ok=True)
        teste = candidato / ".write_test"
        teste.touch()
        teste.unlink()
        return candidato
    except Exception:
        fallback = Path(tempfile.gettempdir()) / "telemonit_logs"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def _run_id_padrao(modulo: str) -> str:
    """Run ID correlacionável: `<modulo>-<EXECUCAO_ID curto>`."""
    exec_curto = os.environ.get("EXECUCAO_ID", "")[:8]
    return f"{modulo}-{exec_curto}" if exec_curto else modulo


def _criar_sink_telemonit(modulo: str):
    """Sink loguru: WARNING -> telemonit.alerta, ERROR/CRITICAL -> telemonit.erro."""

    def sink(message):
        record = message.record
        nivel = record["level"].name
        msg = record["message"]
        contexto: dict[str, Any] = {
            "function": record["function"],
            "line": record["line"],
            "file": record["file"].name,
            "modulo": modulo,
        }
        traceback_str: str | None = None
        if record["exception"]:
            try:
                import traceback as _tb
                exc = record["exception"]
                traceback_str = "".join(
                    _tb.format_exception(exc.type, exc.value, exc.traceback)
                )
            except Exception:
                pass

        run_id = _run_id_padrao(modulo)
        titulo = (msg[:180].splitlines()[0] if msg else f"Evento em {modulo}")
        try:
            if nivel in ("ERROR", "CRITICAL"):
                _notificar.erro(
                    titulo=titulo,
                    detalhes=msg[:1500] if msg else "",
                    contexto=contexto,
                    traceback=traceback_str,
                    run_id=run_id,
                )
            elif nivel == "WARNING":
                _notificar.alerta(
                    titulo=titulo,
                    detalhes=msg[:1500] if msg else "",
                    contexto=contexto,
                    run_id=run_id,
                )
        except Exception:
            # Lib nunca propaga exceção pro caller
            pass

    return sink


# ---------------------------------------------------------------------------
# Logger fallback (sem loguru instalado)
# ---------------------------------------------------------------------------

class _LoggerNoOp:
    """Logger fallback baseado em print(). Mantém integração com telemonit."""

    def __init__(self, modulo: str):
        self._modulo = modulo

    def _emit(self, nivel: str, msg: str) -> None:
        print(f"[{nivel}] {self._modulo} | {msg}", flush=True)

    def _normalize(self, msg: str, args, kwargs) -> str:
        if args or kwargs:
            try:
                return msg.format(*args, **kwargs)
            except Exception:
                return msg
        return msg

    def debug(self, msg, *args, **kwargs):
        self._emit("DEBUG", self._normalize(msg, args, kwargs))

    def info(self, msg, *args, **kwargs):
        self._emit("INFO", self._normalize(msg, args, kwargs))

    def warning(self, msg, *args, **kwargs):
        texto = self._normalize(msg, args, kwargs)
        self._emit("WARNING", texto)
        try:
            _notificar.alerta(
                titulo=texto[:180], detalhes=texto,
                contexto={"modulo": self._modulo}, run_id=_run_id_padrao(self._modulo),
            )
        except Exception:
            pass

    def error(self, msg, *args, **kwargs):
        texto = self._normalize(msg, args, kwargs)
        self._emit("ERROR", texto)
        try:
            _notificar.erro(
                titulo=texto[:180], detalhes=texto,
                contexto={"modulo": self._modulo}, run_id=_run_id_padrao(self._modulo),
            )
        except Exception:
            pass

    def exception(self, msg, *args, **kwargs):
        import traceback as _tb
        texto = self._normalize(msg, args, kwargs)
        tb = _tb.format_exc()
        self._emit("ERROR", f"{texto}\n{tb}")
        try:
            _notificar.erro(
                titulo=texto[:180], detalhes=texto, traceback=tb,
                contexto={"modulo": self._modulo}, run_id=_run_id_padrao(self._modulo),
            )
        except Exception:
            pass

    def critical(self, msg, *args, **kwargs):
        self.error(msg, *args, **kwargs)

    def bind(self, **kwargs):
        return self


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def bootstrap(
    modulo: str,
    projeto: str,
    *,
    logs_dir: Path | str | None = None,
    retention: str = "1 day",
    rotation: str = "10 MB",
    nivel_stdout: str = "INFO",
    nivel_arquivo: str = "DEBUG",
    instalar_excepthook: bool = True,
    compression: str | None = "zip",
):
    """Configura loguru + telemonit + excepthook + sink unificado.

    Args:
        modulo: nome curto do entry point (ex: "zendesk", "ocr"). Vira nome
            do arquivo `logs/<modulo>.log` e raiz do `run_id`.
        projeto: identificador do projeto (ex: "dp_admissao"). Repassado
            para `telemonit.configurar(projeto=...)`.
        logs_dir: pasta dos logs. Default: `<cwd>/logs`. Cai no tempdir se
            sem permissão de escrita.
        retention: retenção dos arquivos `.log`. Default `"1 day"` (limpeza
            automática após 24h pelo loguru).
        rotation: rotação por tamanho. Default `"10 MB"`. Pode ser tempo:
            `"00:00"` (rotaciona à meia-noite).
        nivel_stdout: nível mínimo no terminal. Default `INFO`.
        nivel_arquivo: nível mínimo no arquivo. Default `DEBUG`.
        instalar_excepthook: instala `telemonit.excepthook.instalar()` se True.
        compression: compressão do arquivo rotacionado. Default `"zip"`.

    Returns:
        Logger configurado (loguru ou fallback `_LoggerNoOp`). `warning` e
        `error` automaticamente vão para a Donna via telemonit.
    """
    # 1) telemonit
    try:
        _config.configurar(projeto=projeto)
    except Exception:
        pass

    if instalar_excepthook:
        try:
            _excepthook_mod.instalar()
        except Exception:
            pass

    # 2) loguru (com fallback no-op)
    if not _LOGURU_OK:
        return _LoggerNoOp(modulo)

    log_dir = _resolver_logs_dir(logs_dir)

    _loguru_logger.remove()

    # stdout colorido
    _loguru_logger.add(
        sys.stdout,
        format=(
            "<green>{time:HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{extra[modulo]}</cyan> | "
            "{message}"
        ),
        level=nivel_stdout,
        colorize=True,
        backtrace=False,
        diagnose=False,
    )

    # arquivo com rotation + retention (limpeza automática após `retention`)
    _loguru_logger.add(
        log_dir / f"{modulo}.log",
        format=(
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
            "{extra[modulo]} | {function}:{line} | {message}"
        ),
        level=nivel_arquivo,
        rotation=rotation,
        retention=retention,
        compression=compression,
        encoding="utf-8",
        backtrace=True,
        diagnose=False,  # vaza variáveis em produção
    )

    # sink customizado para telemonit
    _loguru_logger.add(
        _criar_sink_telemonit(modulo),
        level="WARNING",
        format="{message}",
    )

    return _loguru_logger.bind(modulo=modulo)


__all__ = ["bootstrap"]
