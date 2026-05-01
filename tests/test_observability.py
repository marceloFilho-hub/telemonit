"""Testes do bootstrap de observability (loguru + telemonit + sink)."""

import sys

import pytest

from telemonit import config, observability, throttle


@pytest.fixture(autouse=True)
def _ambiente(monkeypatch, tmp_path):
    config.resetar()
    monkeypatch.setenv("MONITOR_PROJETO", "")
    monkeypatch.setenv("MONITOR_TG_TOKEN", "tk")
    monkeypatch.setenv("MONITOR_TG_CHAT_ID", "ch")
    monkeypatch.setenv("MONITOR_DRIVE_LOG_FOLDER", "")
    monkeypatch.setenv("MONITOR_NIVEL", "alerta")

    state = tmp_path / "throttle.json"
    monkeypatch.setattr(throttle, "_STATE_PATH", state)
    throttle._memoria.clear()
    throttle._carregado = False
    yield
    config.resetar()
    throttle._memoria.clear()
    throttle._carregado = False
    # Reseta excepthook para não vazar entre testes
    sys.excepthook = sys.__excepthook__


def test_bootstrap_configura_telemonit(tmp_path, monkeypatch):
    """bootstrap deve chamar config.configurar com o projeto passado."""
    monkeypatch.chdir(tmp_path)
    logger = observability.bootstrap("modtest", projeto="proj_test")

    cfg = config.obter()
    assert cfg["projeto"] == "proj_test"
    assert logger is not None


def test_bootstrap_cria_arquivo_log(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    logger = observability.bootstrap("mod_arquivo", projeto="proj")
    logger.info("mensagem de teste")

    arquivo = tmp_path / "logs" / "mod_arquivo.log"
    assert arquivo.exists()
    conteudo = arquivo.read_text(encoding="utf-8")
    assert "mensagem de teste" in conteudo


def test_bootstrap_run_id_inclui_modulo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("EXECUCAO_ID", "abcdef1234567890")
    observability.bootstrap("mod_x", projeto="p")

    run_id = observability._run_id_padrao("mod_x")
    assert run_id == "mod_x-abcdef12"


def test_bootstrap_run_id_sem_execucao(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("EXECUCAO_ID", raising=False)
    observability.bootstrap("mod_y", projeto="p")

    run_id = observability._run_id_padrao("mod_y")
    assert run_id == "mod_y"


def test_logger_warning_dispara_telemonit_alerta(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    spy = mocker.patch("telemonit.observability._notificar.alerta")
    logger = observability.bootstrap("mod_warn", projeto="proj_warn")

    logger.warning("aviso visivel na donna")

    spy.assert_called_once()
    kwargs = spy.call_args.kwargs
    assert "aviso visivel" in kwargs["titulo"]
    assert kwargs["contexto"]["modulo"] == "mod_warn"


def test_logger_error_dispara_telemonit_erro(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    spy = mocker.patch("telemonit.observability._notificar.erro")
    logger = observability.bootstrap("mod_err", projeto="proj_err")

    logger.error("falhou pesado")

    spy.assert_called_once()
    kwargs = spy.call_args.kwargs
    assert "falhou pesado" in kwargs["titulo"]


def test_logger_exception_inclui_traceback(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    spy = mocker.patch("telemonit.observability._notificar.erro")
    logger = observability.bootstrap("mod_exc", projeto="p")

    try:
        raise ValueError("rebentou")
    except ValueError:
        logger.exception("erro durante operacao")

    kwargs = spy.call_args.kwargs
    assert kwargs["traceback"] is not None
    assert "ValueError" in kwargs["traceback"]


def test_logger_info_nao_dispara_telemonit(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    spy_alerta = mocker.patch("telemonit.observability._notificar.alerta")
    spy_erro = mocker.patch("telemonit.observability._notificar.erro")
    logger = observability.bootstrap("mod_info", projeto="p")

    logger.info("apenas info")

    spy_alerta.assert_not_called()
    spy_erro.assert_not_called()


def test_excepthook_instalado_por_default(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sys.excepthook = sys.__excepthook__  # reset
    observability.bootstrap("mod_eh", projeto="p")

    from telemonit import excepthook as _eh
    assert sys.excepthook is _eh.global_handler


def test_excepthook_pode_ser_desabilitado(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sys.excepthook = sys.__excepthook__
    observability.bootstrap("mod_no_eh", projeto="p", instalar_excepthook=False)

    from telemonit import excepthook as _eh
    assert sys.excepthook is not _eh.global_handler


def test_logs_dir_customizado(tmp_path, monkeypatch):
    custom = tmp_path / "meus_logs"
    monkeypatch.chdir(tmp_path)
    logger = observability.bootstrap("mod_custom", projeto="p", logs_dir=custom)
    logger.info("ola")

    assert (custom / "mod_custom.log").exists()


def test_retention_curto_funciona(tmp_path, monkeypatch):
    """Smoke: retention=1 day passa pra loguru sem erro."""
    monkeypatch.chdir(tmp_path)
    logger = observability.bootstrap("mod_ret", projeto="p", retention="1 day")
    logger.info("teste retention")

    assert (tmp_path / "logs" / "mod_ret.log").exists()
