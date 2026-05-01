"""API pública: erro(), alerta(), info().

Stub inicial — implementação completa virá na Fase 1 (PLANO.md).
"""

from __future__ import annotations


def erro(titulo: str, detalhes: str = "", traceback: str | None = None, contexto: dict | None = None) -> None:
    raise NotImplementedError("notificar.erro será implementado na Fase 1")


def alerta(titulo: str, detalhes: str = "", contexto: dict | None = None) -> None:
    raise NotImplementedError("notificar.alerta será implementado na Fase 1")


def info(titulo: str, detalhes: str = "", contexto: dict | None = None) -> None:
    raise NotImplementedError("notificar.info será implementado na Fase 1")
