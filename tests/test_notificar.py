"""Testes do notificar — orquestração de Telegram + JSONL + throttle."""

import pytest

from telemonit import config, notificar, throttle


@pytest.fixture(autouse=True)
def _config_basica(monkeypatch, tmp_path):
    config.resetar()
    monkeypatch.setenv("MONITOR_PROJETO", "proj_teste")
    monkeypatch.setenv("MONITOR_TG_TOKEN", "token_xyz")
    monkeypatch.setenv("MONITOR_TG_CHAT_ID", "chat_abc")
    monkeypatch.setenv("MONITOR_DRIVE_LOG_FOLDER", "folder_id_xyz")
    monkeypatch.setenv("MONITOR_NIVEL", "alerta")

    state_file = tmp_path / "throttle.json"
    monkeypatch.setattr(throttle, "_STATE_PATH", state_file)
    throttle._memoria.clear()
    throttle._carregado = False
    yield
    throttle._memoria.clear()
    throttle._carregado = False
    config.resetar()


def test_erro_dispara_telegram_e_jsonl(mocker):
    spy_tg = mocker.patch("telemonit.notificar.telegram_client.send_text", return_value=True)
    spy_log = mocker.patch("telemonit.notificar.event_log.append_event", return_value=True)
    mocker.patch("telemonit.notificar.drive_resolver.resolver", side_effect=lambda v: v)

    notificar.erro(titulo="Pipeline travou", detalhes="Erro X")

    spy_log.assert_called_once()
    spy_tg.assert_called_once()
    folder, projeto, evento = spy_log.call_args[0]
    assert folder == "folder_id_xyz"
    assert projeto == "proj_teste"
    assert evento["nivel"] == "erro"
    assert evento["titulo"] == "Pipeline travou"


def test_alerta_aplica_throttle(mocker):
    spy_tg = mocker.patch("telemonit.notificar.telegram_client.send_text", return_value=True)
    mocker.patch("telemonit.notificar.event_log.append_event", return_value=True)
    mocker.patch("telemonit.notificar.drive_resolver.resolver", side_effect=lambda v: v)

    notificar.alerta(titulo="Quota alta")
    notificar.alerta(titulo="Quota alta")  # segundo dentro do TTL — bloqueado

    assert spy_tg.call_count == 1


def test_info_grava_jsonl_mas_nao_envia_telegram_no_nivel_alerta(mocker):
    spy_tg = mocker.patch("telemonit.notificar.telegram_client.send_text", return_value=True)
    spy_log = mocker.patch("telemonit.notificar.event_log.append_event", return_value=True)
    mocker.patch("telemonit.notificar.drive_resolver.resolver", side_effect=lambda v: v)

    notificar.info(titulo="Pipeline OK")

    spy_log.assert_called_once()
    spy_tg.assert_not_called()


def test_info_envia_telegram_quando_nivel_minimo_e_info(monkeypatch, mocker):
    monkeypatch.setenv("MONITOR_NIVEL", "info")
    spy_tg = mocker.patch("telemonit.notificar.telegram_client.send_text", return_value=True)
    mocker.patch("telemonit.notificar.event_log.append_event", return_value=True)
    mocker.patch("telemonit.notificar.drive_resolver.resolver", side_effect=lambda v: v)

    notificar.info(titulo="Pipeline OK")

    spy_tg.assert_called_once()


def test_falha_em_telegram_nao_propaga(mocker):
    mocker.patch("telemonit.notificar.event_log.append_event", return_value=True)
    mocker.patch(
        "telemonit.notificar.telegram_client.send_text",
        side_effect=Exception("nao deveria quebrar"),
    )
    mocker.patch("telemonit.notificar.drive_resolver.resolver", side_effect=lambda v: v)

    notificar.erro(titulo="X")  # não deve levantar


def test_falha_em_jsonl_nao_propaga(mocker):
    mocker.patch(
        "telemonit.notificar.event_log.append_event",
        side_effect=Exception("drive offline"),
    )
    spy_tg = mocker.patch("telemonit.notificar.telegram_client.send_text", return_value=True)
    mocker.patch("telemonit.notificar.drive_resolver.resolver", side_effect=lambda v: v)

    notificar.erro(titulo="Y")
    # Telegram ainda deve ser tentado mesmo com JSONL falhando
    spy_tg.assert_called_once()


def test_resolver_traduz_drive_prefix_em_token_e_chat(mocker, monkeypatch):
    monkeypatch.setenv("MONITOR_TG_TOKEN", "drive:token_file_id")
    monkeypatch.setenv("MONITOR_TG_CHAT_ID", "drive:chat_file_id")
    mocker.patch("telemonit.notificar.event_log.append_event", return_value=True)
    spy_tg = mocker.patch("telemonit.notificar.telegram_client.send_text", return_value=True)
    spy_resolver = mocker.patch(
        "telemonit.notificar.drive_resolver.resolver",
        side_effect=lambda v: f"resolvido[{v}]",
    )

    notificar.erro(titulo="Z")

    assert spy_resolver.call_count >= 2
    args = spy_tg.call_args[0]
    token, chat_id, _msg = args[0], args[1], args[2]
    assert token == "resolvido[drive:token_file_id]"
    assert chat_id == "resolvido[drive:chat_file_id]"


def test_construir_evento_traz_campos_obrigatorios():
    evento = notificar._construir_evento(
        nivel="erro", titulo="t", detalhes="d", traceback=None,
        contexto={"a": 1}, projeto="px",
    )
    for campo in ("timestamp", "projeto", "host", "nivel", "titulo", "detalhes", "contexto"):
        assert campo in evento
    assert evento["projeto"] == "px"
    assert evento["nivel"] == "erro"
    assert evento["contexto"] == {"a": 1}


def test_formatar_telegram_inclui_titulo_e_contexto():
    evento = notificar._construir_evento(
        nivel="erro", titulo="Pipe X", detalhes="Detalhe",
        traceback=None, contexto={"empresa": "ACME"}, projeto="proj",
    )
    msg = notificar._formatar_telegram(evento)
    assert "Pipe X" in msg
    assert "ACME" in msg
    assert "ERRO" in msg
    assert "proj" in msg
