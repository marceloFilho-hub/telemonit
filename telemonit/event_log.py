"""Persistência de eventos como JSONL no Google Drive.

Padrão: 1 arquivo por (projeto, mês). Linha = JSON do evento.
Nomeclatura: `eventos_{projeto}_{YYYY-MM}.jsonl`.

Estratégia de append: read-modify-write (download → concat → upload).
Concorrência baixa (1 escritor por arquivo) torna isso aceitável para o MVP.
"""

from __future__ import annotations

import io
import json
from datetime import datetime, timezone

from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

from . import drive_resolver

MIMETYPE_JSONL = "application/x-ndjson"


def append_event(folder_id: str, projeto: str, evento: dict) -> bool:
    """Acrescenta evento ao JSONL do projeto+mês na pasta do Drive.

    Retorna True em sucesso, False em qualquer falha (silenciosa).
    """
    if not folder_id or not projeto:
        return False

    try:
        service = drive_resolver._drive_service()
        nome = _nome_arquivo_mes(projeto)
        linha = (json.dumps(evento, ensure_ascii=False, default=str) + "\n").encode("utf-8")

        file_id = _buscar_arquivo(service, folder_id, nome)
        if file_id is not None:
            atual = _baixar_arquivo(service, file_id)
            _atualizar_arquivo(service, file_id, atual + linha)
        else:
            _criar_arquivo(service, folder_id, nome, linha)
        return True
    except Exception:
        return False


def _nome_arquivo_mes(projeto: str) -> str:
    agora = datetime.now(timezone.utc)
    return f"eventos_{projeto}_{agora.strftime('%Y-%m')}.jsonl"


def _buscar_arquivo(service, folder_id: str, nome: str) -> str | None:
    nome_escapado = nome.replace("'", "\\'")
    query = (
        f"name = '{nome_escapado}' and '{folder_id}' in parents and trashed = false"
    )
    resp = service.files().list(
        q=query,
        fields="files(id, name)",
        spaces="drive",
        pageSize=1,
    ).execute()
    arquivos = resp.get("files", [])
    return arquivos[0]["id"] if arquivos else None


def _baixar_arquivo(service, file_id: str) -> bytes:
    request = service.files().get_media(fileId=file_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buffer.getvalue()


def _atualizar_arquivo(service, file_id: str, conteudo: bytes) -> None:
    media = MediaIoBaseUpload(
        io.BytesIO(conteudo), mimetype=MIMETYPE_JSONL, resumable=False
    )
    service.files().update(fileId=file_id, media_body=media).execute()


def _criar_arquivo(service, folder_id: str, nome: str, conteudo: bytes) -> None:
    media = MediaIoBaseUpload(
        io.BytesIO(conteudo), mimetype=MIMETYPE_JSONL, resumable=False
    )
    metadata = {"name": nome, "parents": [folder_id]}
    service.files().create(body=metadata, media_body=media, fields="id").execute()
