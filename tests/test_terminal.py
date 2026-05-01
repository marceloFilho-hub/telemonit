"""Testes do capturar_terminal."""

import sys

import pytest

import telemonit
from telemonit import config, terminal, throttle


@pytest.fixture(autouse=True)
def _ambiente_isolado(monkeypatch, tmp_path):
    config.resetar()
    monkeypatch.setenv("MONITOR_PROJETO", "proj_term")
    monkeypatch.setenv("MONITOR_TG_TOKEN", "tk")
    monkeypatch.setenv("MONITOR_TG_CHAT_ID", "ch")
    monkeypatch.setenv("MONITOR_DRIVE_LOG_FOLDER", "fid")
    monkeypatch.setenv("MONITOR_NIVEL", "alerta")

    state = tmp_path / "throttle.json"
    monkeypatch.setattr(throttle, "_STATE_PATH", state)
    throttle._memoria.clear()
    throttle._carregado = False
    yield
    config.resetar()
    throttle._memoria.clear()
    throttle._carregado = False


def test_saida_normal_nao_dispara_erro(mocker):
    spy = mocker.patch("telemonit.terminal.notificar.erro")
    with telemonit.capturar_terminal(run_id="run-ok"):
        print("tudo certo")
    spy.assert_not_called()


def test_excecao_dispara_notificar_erro_e_re_levanta(mocker):
    spy = mocker.patch("telemonit.terminal.notificar.erro")
    with pytest.raises(ValueError, match="boom"):
        with telemonit.capturar_terminal(run_id="run-001"):
            raise ValueError("boom")

    spy.assert_called_once()
    kwargs = spy.call_args.kwargs
    assert kwargs["run_id"] == "run-001"
    assert "boom" in kwargs["detalhes"]
    assert kwargs["traceback"] is not None
    assert "ValueError" in kwargs["traceback"]


def test_inclui_stderr_capturado_em_detalhes(mocker):
    spy = mocker.patch("telemonit.terminal.notificar.erro")
    with pytest.raises(RuntimeError):
        with telemonit.capturar_terminal(run_id="r1"):
            print("antes do erro", file=sys.stderr)
            raise RuntimeError("falha")

    detalhes = spy.call_args.kwargs["detalhes"]
    assert "antes do erro" in detalhes
    assert "[stderr final]" in detalhes


def test_inclui_stdout_capturado_em_detalhes(mocker):
    spy = mocker.patch("telemonit.terminal.notificar.erro")
    with pytest.raises(RuntimeError):
        with telemonit.capturar_terminal(run_id="r2"):
            print("processando passo 1")
            print("processando passo 2")
            raise RuntimeError("erro no passo 3")

    detalhes = spy.call_args.kwargs["detalhes"]
    assert "[stdout final]" in detalhes
    assert "passo 1" in detalhes


def test_incluir_saida_false_omite_buffers(mocker):
    spy = mocker.patch("telemonit.terminal.notificar.erro")
    with pytest.raises(ValueError):
        with telemonit.capturar_terminal(run_id="r3", incluir_saida=False):
            print("ruido stdout")
            raise ValueError("x")

    detalhes = spy.call_args.kwargs["detalhes"]
    assert "ruido stdout" not in detalhes
    assert "[stdout final]" not in detalhes


def test_titulo_personalizado(mocker):
    spy = mocker.patch("telemonit.terminal.notificar.erro")
    with pytest.raises(Exception):
        with telemonit.capturar_terminal(
            run_id="r4", titulo_erro="Pipeline X falhou"
        ):
            raise Exception("y")
    assert spy.call_args.kwargs["titulo"] == "Pipeline X falhou"


def test_run_id_opcional(mocker):
    spy = mocker.patch("telemonit.terminal.notificar.erro")
    with pytest.raises(Exception):
        with telemonit.capturar_terminal():
            raise Exception("z")
    assert spy.call_args.kwargs["run_id"] is None


def test_terminal_e_restaurado_apos_excecao():
    out_orig = sys.stdout
    err_orig = sys.stderr
    with pytest.raises(Exception):
        with telemonit.capturar_terminal():
            assert sys.stdout is not out_orig
            raise Exception("x")
    assert sys.stdout is out_orig
    assert sys.stderr is err_orig


def test_terminal_e_restaurado_apos_saida_normal():
    out_orig = sys.stdout
    err_orig = sys.stderr
    with telemonit.capturar_terminal():
        pass
    assert sys.stdout is out_orig
    assert sys.stderr is err_orig


def test_falha_em_notificar_nao_impede_re_raise(mocker):
    mocker.patch(
        "telemonit.terminal.notificar.erro",
        side_effect=Exception("notificar quebrou"),
    )
    with pytest.raises(ValueError, match="original"):
        with telemonit.capturar_terminal(run_id="x"):
            raise ValueError("original")


def test_tee_preserva_terminal(capsys):
    with telemonit.capturar_terminal(run_id="tee"):
        print("mensagem visível no terminal")

    captured = capsys.readouterr()
    assert "mensagem visível no terminal" in captured.out
