"""Testes do fallback local do event_log quando o Drive falha."""

import json

import pytest

from telemonit import event_log


def test_drive_falhando_grava_em_arquivo_local(monkeypatch, tmp_path):
    """Quando _drive_service levanta, evento vai pro JSONL local de fallback."""
    monkeypatch.setattr(event_log, "_PASTA_FALLBACK_HOME", tmp_path)

    def _drive_service_quebrado():
        raise RuntimeError("SA sem permissão")

    monkeypatch.setattr(
        event_log.drive_resolver, "_drive_service", _drive_service_quebrado
    )

    evento = {"nivel": "erro", "titulo": "teste fallback", "host": "localhost"}
    ok = event_log.append_event("folder_qualquer", "proj_x", evento)

    assert ok is True
    arquivo_local = event_log.caminho_fallback_local("proj_x")
    assert arquivo_local.exists()
    conteudo = arquivo_local.read_text(encoding="utf-8")
    linhas = [line for line in conteudo.splitlines() if line]
    assert len(linhas) == 1
    obj = json.loads(linhas[0])
    assert obj["titulo"] == "teste fallback"
    # Fallback adiciona metadata sobre a falha
    assert "_telemonit_fallback" in obj
    assert "RuntimeError" in obj["_telemonit_fallback"]["drive_erro"]


def test_folder_id_vazio_nao_grava_em_local(monkeypatch, tmp_path):
    """folder_id vazio = usuário desabilitou Drive. Não cria fallback local."""
    monkeypatch.setattr(event_log, "_PASTA_FALLBACK_HOME", tmp_path)

    ok = event_log.append_event("", "proj_y", {"a": 1})

    assert ok is False
    arquivo_local = event_log._PASTA_FALLBACK_HOME / "proj_y"
    assert not arquivo_local.exists() or not list(arquivo_local.glob("*.jsonl"))


def test_projeto_vazio_retorna_false(monkeypatch, tmp_path):
    monkeypatch.setattr(event_log, "_PASTA_FALLBACK_HOME", tmp_path)
    assert event_log.append_event("folder", "", {"x": 1}) is False


def test_drive_ok_nao_grava_local(monkeypatch, tmp_path, mocker):
    """Quando Drive responde, evento NÃO vai pra local."""
    monkeypatch.setattr(event_log, "_PASTA_FALLBACK_HOME", tmp_path)

    fake_service = mocker.MagicMock()
    monkeypatch.setattr(
        event_log.drive_resolver, "_drive_service", lambda: fake_service
    )
    monkeypatch.setattr(event_log, "_buscar_arquivo", lambda *a, **kw: None)
    monkeypatch.setattr(event_log, "_criar_arquivo", lambda *a, **kw: None)

    ok = event_log.append_event("folder_real", "proj_drive_ok", {"x": 1})

    assert ok is True
    pasta_local = tmp_path / "proj_drive_ok"
    assert not pasta_local.exists() or not list(pasta_local.glob("*.jsonl"))


def test_multiplos_eventos_fallback_acumulam(monkeypatch, tmp_path):
    """Falhas sucessivas do Drive acumulam no mesmo JSONL local."""
    monkeypatch.setattr(event_log, "_PASTA_FALLBACK_HOME", tmp_path)
    monkeypatch.setattr(
        event_log.drive_resolver, "_drive_service",
        lambda: (_ for _ in ()).throw(RuntimeError("offline")),
    )

    for i in range(3):
        event_log.append_event("folder", "proj_z", {"i": i, "msg": f"evento_{i}"})

    arquivo = event_log.caminho_fallback_local("proj_z")
    linhas = [line for line in arquivo.read_text(encoding="utf-8").splitlines() if line]
    assert len(linhas) == 3
    valores_i = [json.loads(line)["i"] for line in linhas]
    assert valores_i == [0, 1, 2]
