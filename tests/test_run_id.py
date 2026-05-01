"""Testes para run_id como campo first-class no evento."""

import pytest

from telemonit import config, notificar, throttle


@pytest.fixture(autouse=True)
def _ambiente(monkeypatch, tmp_path):
    config.resetar()
    monkeypatch.setenv("MONITOR_PROJETO", "p")
    monkeypatch.setenv("MONITOR_TG_TOKEN", "t")
    monkeypatch.setenv("MONITOR_TG_CHAT_ID", "c")
    monkeypatch.setenv("MONITOR_DRIVE_LOG_FOLDER", "f")
    monkeypatch.setenv("MONITOR_NIVEL", "alerta")

    state = tmp_path / "throttle.json"
    monkeypatch.setattr(throttle, "_STATE_PATH", state)
    throttle._memoria.clear()
    throttle._carregado = False
    yield
    config.resetar()
    throttle._memoria.clear()
    throttle._carregado = False


def test_evento_tem_run_id_quando_fornecido():
    evento = notificar._construir_evento(
        nivel="erro", titulo="t", detalhes="d", traceback=None,
        contexto=None, projeto="p", run_id="run-42",
    )
    assert evento["run_id"] == "run-42"


def test_evento_run_id_none_quando_omitido():
    evento = notificar._construir_evento(
        nivel="info", titulo="t", detalhes="d", traceback=None,
        contexto=None, projeto="p", run_id=None,
    )
    assert evento["run_id"] is None


def test_erro_passa_run_id_ao_jsonl(mocker):
    spy_log = mocker.patch("telemonit.notificar.event_log.append_event", return_value=True)
    mocker.patch("telemonit.notificar.telegram_client.send_text", return_value=True)
    mocker.patch("telemonit.notificar.drive_resolver.resolver", side_effect=lambda v: v)

    notificar.erro(titulo="x", run_id="run-abc")

    evento = spy_log.call_args[0][2]
    assert evento["run_id"] == "run-abc"


def test_alerta_throttle_separa_runs_diferentes(mocker):
    spy_tg = mocker.patch("telemonit.notificar.telegram_client.send_text", return_value=True)
    mocker.patch("telemonit.notificar.event_log.append_event", return_value=True)
    mocker.patch("telemonit.notificar.drive_resolver.resolver", side_effect=lambda v: v)

    notificar.alerta(titulo="Quota alta", run_id="run-A")
    notificar.alerta(titulo="Quota alta", run_id="run-A")  # bloqueado
    notificar.alerta(titulo="Quota alta", run_id="run-B")  # passa (run diferente)

    assert spy_tg.call_count == 2


def test_alerta_throttle_sem_run_id_continua_funcionando(mocker):
    spy_tg = mocker.patch("telemonit.notificar.telegram_client.send_text", return_value=True)
    mocker.patch("telemonit.notificar.event_log.append_event", return_value=True)
    mocker.patch("telemonit.notificar.drive_resolver.resolver", side_effect=lambda v: v)

    notificar.alerta(titulo="X")
    notificar.alerta(titulo="X")

    assert spy_tg.call_count == 1


def test_telegram_inclui_run_id_no_cabecalho():
    evento = notificar._construir_evento(
        nivel="erro", titulo="t", detalhes="", traceback=None,
        contexto=None, projeto="proj", run_id="run-xyz",
    )
    msg = notificar._formatar_telegram(evento)
    assert "run-xyz" in msg


def test_telegram_omite_run_id_quando_ausente():
    evento = notificar._construir_evento(
        nivel="erro", titulo="t", detalhes="", traceback=None,
        contexto=None, projeto="proj", run_id=None,
    )
    msg = notificar._formatar_telegram(evento)
    assert "run " not in msg.split("\n")[0]  # primeira linha não tem `run `
