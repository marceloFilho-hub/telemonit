"""Handler global para sys.excepthook — captura exceções não tratadas
e as envia via notificar.erro antes de delegar ao excepthook original.

Uso:
    from telemonit import excepthook
    excepthook.instalar()
"""

from __future__ import annotations

import sys
import traceback as tb_module

from . import notificar

_excepthook_original = None


def global_handler(exc_type, exc_value, exc_traceback) -> None:
    """Captura exceção e dispara notificar.erro, depois delega ao handler original."""
    try:
        tb_str = "".join(tb_module.format_exception(exc_type, exc_value, exc_traceback))
        notificar.erro(
            titulo=f"{exc_type.__name__}: {exc_value}",
            detalhes="Exceção não tratada no processo principal",
            traceback=tb_str,
        )
    except Exception:
        pass

    if _excepthook_original is not None:
        _excepthook_original(exc_type, exc_value, exc_traceback)
    else:
        sys.__excepthook__(exc_type, exc_value, exc_traceback)


def instalar() -> None:
    """Instala o handler global em sys.excepthook (idempotente)."""
    global _excepthook_original
    if sys.excepthook is global_handler:
        return
    _excepthook_original = sys.excepthook
    sys.excepthook = global_handler


def desinstalar() -> None:
    """Restaura o excepthook anterior (útil para testes)."""
    global _excepthook_original
    if sys.excepthook is global_handler and _excepthook_original is not None:
        sys.excepthook = _excepthook_original
    _excepthook_original = None
