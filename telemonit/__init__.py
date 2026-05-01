"""telemonit — notificações centralizadas (Telegram + Drive JSONL)."""

__version__ = "0.1.0"

from . import excepthook, notificar

__all__ = ["notificar", "excepthook", "__version__"]
