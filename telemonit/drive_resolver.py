"""Resolve referências `drive:<file_id>` para o conteúdo real do arquivo no Google Drive.

Padrão extraído de conciliador_prolabore/src/monitor/email_monitor.py
(`_resolver_secrets_drive`) e generalizado.

Service Account é carregada de GOOGLE_APPLICATION_CREDENTIALS.
"""

from __future__ import annotations

import io
import os
from functools import lru_cache

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

PREFIXO_DRIVE = "drive:"
SCOPES_DRIVE = ["https://www.googleapis.com/auth/drive"]


@lru_cache(maxsize=1)
def _drive_service():
    """Retorna o cliente Drive autenticado (lazy + cached)."""
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds_path or not os.path.exists(creds_path):
        raise RuntimeError(
            f"GOOGLE_APPLICATION_CREDENTIALS não configurado ou caminho inválido: {creds_path!r}"
        )
    creds = service_account.Credentials.from_service_account_file(
        creds_path, scopes=SCOPES_DRIVE
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


@lru_cache(maxsize=128)
def _baixar_conteudo(file_id: str) -> str:
    """Baixa o conteúdo do arquivo (texto UTF-8)."""
    service = _drive_service()
    request = service.files().get_media(fileId=file_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buffer.getvalue().decode("utf-8").strip()


def resolver(valor: str | None) -> str | None:
    """Resolve um valor potencialmente prefixado com `drive:`.

    - `None` → `None`
    - string sem prefixo `drive:` → retorna como veio
    - `drive:<id>` → baixa o arquivo do Drive e retorna o conteúdo
    """
    if valor is None:
        return None
    if not isinstance(valor, str):
        return valor
    if not valor.startswith(PREFIXO_DRIVE):
        return valor
    file_id = valor[len(PREFIXO_DRIVE):].strip()
    if not file_id:
        return ""
    return _baixar_conteudo(file_id)


def limpar_cache() -> None:
    """Limpa cache do service e de conteúdos baixados (útil para testes)."""
    _drive_service.cache_clear()
    _baixar_conteudo.cache_clear()
