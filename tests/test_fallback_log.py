"""Testes do log de fallback no _emitir (rastro de falhas internas)."""

import pytest

from telemonit import config, notificar, throttle


@pytest.fixture(autouse=True)
def _ambiente(monkeypatch, tmp_path):
    config.resetar()
    monkeypatch.setenv("MONITOR_PROJETO", "proj_fb")
    monkeypatch.setenv("MONITOR_TG_TOKEN", "token")
    monkeypatch.setenv("MONITOR_TG_CHAT_ID", "chat")
    monkeypatch.setenv("MONITOR_DRIVE_LOG_FOLDER", "folder_fake")
    monkeypatch.setenv("MONITOR_NIVEL", "alerta")

    fallback = tmp_path / "telemonit_fallback.log"
    monkeypatch.setattr(notificar, "_FALLBACK_LOG_PATH", fallback)

    state = tmp_path / "throttle.json"
    monkeypatch.setattr(throttle, "_STATE_PATH", state)
    throttle._memoria.clear()
    throttle._carregado = False
    yield fallback
    config.resetar()
    throttle._memoria.clear()
    throttle._carregado = False


def test_send_text_retorna_false_grava_fallback(_ambiente, mocker):
    fallback = _ambiente
    mocker.patch("telemonit.notificar.event_log.append_event", return_value=True)
    mocker.patch("telemonit.notificar.drive_resolver.resolver", side_effect=lambda v: v)
    mocker.patch("telemonit.notificar.telegram_client.send_text", return_value=False)

    notificar.erro(titulo="x")

    assert fallback.exists()
    conteudo = fallback.read_text(encoding="utf-8")
    assert "telegram_client.send_text retornou False" in conteudo


def test_send_text_levanta_grava_fallback(_ambiente, mocker):
    fallback = _ambiente
    mocker.patch("telemonit.notificar.event_log.append_event", return_value=True)
    mocker.patch("telemonit.notificar.drive_resolver.resolver", side_effect=lambda v: v)
    mocker.patch(
        "telemonit.notificar.telegram_client.send_text",
        side_effect=RuntimeError("nao conectou"),
    )

    notificar.erro(titulo="y")

    conteudo = fallback.read_text(encoding="utf-8")
    assert "telegram falhou: RuntimeError: nao conectou" in conteudo


def test_event_log_levanta_grava_fallback(_ambiente, mocker):
    fallback = _ambiente
    mocker.patch(
        "telemonit.notificar.event_log.append_event",
        side_effect=RuntimeError("drive offline"),
    )
    mocker.patch("telemonit.notificar.drive_resolver.resolver", side_effect=lambda v: v)
    mocker.patch("telemonit.notificar.telegram_client.send_text", return_value=True)

    notificar.erro(titulo="z")

    conteudo = fallback.read_text(encoding="utf-8")
    assert "event_log falhou: RuntimeError: drive offline" in conteudo


def test_emitir_falha_geral_grava_fallback(_ambiente, mocker):
    """Falha em _construir_evento (caminho ainda mais raro) também loga."""
    fallback = _ambiente
    mocker.patch(
        "telemonit.notificar._construir_evento",
        side_effect=RuntimeError("falha estrutural"),
    )

    notificar.erro(titulo="w")

    conteudo = fallback.read_text(encoding="utf-8")
    assert "_emitir engoliu exception" in conteudo
    assert "falha estrutural" in conteudo


def test_caso_normal_nao_polui_fallback(_ambiente, mocker):
    """Quando tudo dá certo, fallback log fica vazio."""
    fallback = _ambiente
    mocker.patch("telemonit.notificar.event_log.append_event", return_value=True)
    mocker.patch("telemonit.notificar.drive_resolver.resolver", side_effect=lambda v: v)
    mocker.patch("telemonit.notificar.telegram_client.send_text", return_value=True)

    notificar.erro(titulo="ok")

    assert not fallback.exists() or fallback.read_text(encoding="utf-8") == ""
