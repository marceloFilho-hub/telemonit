"""telemonit — notificações centralizadas (Telegram + Drive JSONL)."""

__version__ = "0.3.0"

from . import config, excepthook, notificar, terminal
from .config import configurar
from .notificar import alerta, erro, info
from .terminal import capturar_terminal

# observability é import opcional — depende de loguru. Quem quiser usar
# importa diretamente de `telemonit.observability`.
try:
    from . import observability  # noqa: F401
    from .observability import bootstrap as _observability_bootstrap  # noqa: F401
    _OBSERVABILITY_DISPONIVEL = True
except Exception:
    _OBSERVABILITY_DISPONIVEL = False

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

