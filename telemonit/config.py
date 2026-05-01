"""Configuração programática da lib (estilo `pd.set_option`).

Precedência de resolução:
    1. Valores passados em `telemonit.configurar(...)`
    2. Variáveis de ambiente (`MONITOR_*`)
    3. Defaults internos
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class _Configuracao:
    projeto: str | None = None
    telegram_token: str | None = None
    telegram_chat_id: str | None = None
    drive_folder: str | None = None
    nivel: str | None = None  # info | alerta | erro

    def aplicar(self, **kwargs) -> None:
        """Atualiza apenas os campos que foram explicitamente passados (não-None)."""
        for chave, valor in kwargs.items():
            if not hasattr(self, chave):
                raise TypeError(f"Parâmetro desconhecido: {chave!r}")
            if valor is not None:
                setattr(self, chave, valor)

    def resolver(self) -> dict:
        """Resolve config consultando programática → env → default."""
        return {
            "projeto": self.projeto or os.environ.get("MONITOR_PROJETO", "desconhecido"),
            "tg_token_raw": self.telegram_token or os.environ.get("MONITOR_TG_TOKEN", ""),
            "tg_chat_id_raw": self.telegram_chat_id or os.environ.get("MONITOR_TG_CHAT_ID", ""),
            "drive_folder": self.drive_folder or os.environ.get("MONITOR_DRIVE_LOG_FOLDER", ""),
            "nivel_minimo": (self.nivel or os.environ.get("MONITOR_NIVEL", "alerta")).lower(),
        }


_estado = _Configuracao()


def configurar(
    *,
    projeto: str | None = None,
    telegram_token: str | None = None,
    telegram_chat_id: str | None = None,
    drive_folder: str | None = None,
    nivel: str | None = None,
) -> None:
    """Configura a lib programaticamente.

    Sobrescreve as variáveis de ambiente correspondentes apenas para os
    parâmetros explicitamente passados (os demais continuam vindo do `.env`).

    Args:
        projeto: identificador do projeto cliente.
        telegram_token: token do bot. Aceita `drive:<file_id>`.
        telegram_chat_id: chat_id do destino. Aceita `drive:<file_id>`.
        drive_folder: ID da pasta do Drive para os JSONL.
        nivel: nível mínimo para envio Telegram (`info` | `alerta` | `erro`).
    """
    _estado.aplicar(
        projeto=projeto,
        telegram_token=telegram_token,
        telegram_chat_id=telegram_chat_id,
        drive_folder=drive_folder,
        nivel=nivel,
    )


def obter() -> dict:
    """Retorna a config efetiva (programática + env + defaults)."""
    return _estado.resolver()


def resetar() -> None:
    """Zera a configuração programática (útil para testes)."""
    global _estado
    _estado = _Configuracao()
