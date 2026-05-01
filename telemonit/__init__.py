"""telemonit — notificações centralizadas (Telegram + Drive JSONL)."""

__version__ = "0.1.0"

from . import config, excepthook, notificar
from .config import configurar
from .notificar import alerta, erro, info

__all__ = [
    "configurar",
    "erro",
    "alerta",
    "info",
    "config",
    "notificar",
    "excepthook",
    "__version__",
]
