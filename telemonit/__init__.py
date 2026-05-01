"""telemonit — notificações centralizadas (Telegram + Drive JSONL)."""

__version__ = "0.2.0"

from . import config, excepthook, notificar, terminal
from .config import configurar
from .notificar import alerta, erro, info
from .terminal import capturar_terminal

__all__ = [
    "configurar",
    "erro",
    "alerta",
    "info",
    "capturar_terminal",
    "config",
    "notificar",
    "excepthook",
    "terminal",
    "__version__",
]
