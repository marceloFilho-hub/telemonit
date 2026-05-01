"""Persistência de eventos como JSONL no Google Drive — com fallback local.

Padrão: 1 arquivo por (projeto, mês). Linha = JSON do evento.
Nomeclatura: `eventos_{projeto}_{YYYY-MM}.jsonl`.

Estratégia de append no Drive: read-modify-write (download → concat → upload).
Concorrência baixa (1 escritor por arquivo) torna isso aceitável para o MVP.

Fallback local: quando o Drive está habilitado mas falha (offline, SA sem
permissão, quota), o evento é gravado em
`~/.telemonit/<projeto>/eventos_{projeto}_{YYYY-MM}.jsonl` para preservar
o audit trail. Se o `folder_id` não foi configurado (usuário desabilitou
Drive), nada é gravado localmente — comportamento original preservado.
"""

from __future__ import annotations

import io
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

from . import drive_resolver

MIMETYPE_JSONL = "application/x-ndjson"

# Onde gravar o JSONL de fallback quando o Drive falhar.
# Prioridade: ~/.telemonit/<projeto>/. Fallback final: tempdir.
_PASTA_FALLBACK_HOME = Path.home() / ".telemonit"


def append_event(folder_id: str, projeto: str, evento: dict) -> bool:
    """Acrescenta evento ao JSONL do projeto+mês.

    Caminhos:
    - `folder_id` setado e Drive responde: grava no Drive (retorna True).
    - `folder_id` setado mas Drive falhou: grava no JSONL local de fallback
      (`~/.telemonit/<projeto>/eventos_*.jsonl`) e retorna True. Audit trail
      preservado, sem perder eventos por instabilidade do Drive.
    - `folder_id` vazio (Drive desabilitado): retorna False sem gravar nada
      — preserva escolha do usuário que setou `MONITOR_DRIVE_LOG_FOLDER=`.
    - `projeto` vazio: retorna False (input inválido).
    """
    if not projeto:
        return False

    if not folder_id:
        return False

    try:
        service = drive_resolver._drive_service()
        nome = _nome_arquivo_mes(projeto)
        linha = _serializar_linha(evento)

        file_id = _buscar_arquivo(service, folder_id, nome)
        if file_id is not None:
            atual = _baixar_arquivo(service, file_id)
            _atualizar_arquivo(service, file_id, atual + linha)
        else:
            _criar_arquivo(service, folder_id, nome, linha)
        return True
    except Exception as exc:
        # Drive falhou — tenta fallback local para não perder o evento.
        return _gravar_fallback_local(projeto, evento, motivo_falha=exc)


def _serializar_linha(evento: dict) -> bytes:
    return (json.dumps(evento, ensure_ascii=False, default=str) + "\n").encode("utf-8")


def _nome_arquivo_mes(projeto: str) -> str:
    agora = datetime.now(timezone.utc)
    return f"eventos_{projeto}_{agora.strftime('%Y-%m')}.jsonl"


def caminho_fallback_local(projeto: str) -> Path:
    """Retorna o caminho onde o fallback JSONL é/seria gravado para `projeto`.

    Útil para o caller saber onde olhar em caso de Drive offline.
    """
    candidato = _PASTA_FALLBACK_HOME / projeto
    try:
        candidato.mkdir(parents=True, exist_ok=True)
        return candidato / _nome_arquivo_mes(projeto)
    except Exception:
        d = Path(tempfile.gettempdir()) / "telemonit" / projeto
        d.mkdir(parents=True, exist_ok=True)
        return d / _nome_arquivo_mes(projeto)


def _gravar_fallback_local(projeto: str, evento: dict, motivo_falha: Exception | None = None) -> bool:
    """Grava o evento em arquivo JSONL local quando o Drive falhar."""
    try:
        caminho = caminho_fallback_local(projeto)
        # Anexa o motivo da falha ao evento para diagnóstico futuro
        if motivo_falha is not None:
            ev = dict(evento)
            ev.setdefault("_telemonit_fallback", {})
            ev["_telemonit_fallback"] = {
                "drive_erro": f"{type(motivo_falha).__name__}: {motivo_falha}",
                "fallback_em": datetime.now(timezone.utc).isoformat(),
            }
        else:
            ev = evento
        with caminho.open("ab") as f:
            f.write(_serializar_linha(ev))
        return True
    except Exception:
        return False


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
