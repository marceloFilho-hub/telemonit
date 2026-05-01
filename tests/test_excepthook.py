"""Testes do excepthook."""

import sys

import pytest

from telemonit import excepthook


@pytest.fixture(autouse=True)
def _restaurar_excepthook():
    original = sys.excepthook
    yield
    sys.excepthook = original
    excepthook._excepthook_original = None


def test_instalar_substitui_excepthook():
    assert sys.excepthook is not excepthook.global_handler
    excepthook.instalar()
    assert sys.excepthook is excepthook.global_handler


def test_instalar_idempotente():
    excepthook.instalar()
    primeiro = excepthook._excepthook_original
    excepthook.instalar()
    assert excepthook._excepthook_original is primeiro


def test_desinstalar_restaura_anterior():
    original = sys.excepthook
    excepthook.instalar()
    excepthook.desinstalar()
    assert sys.excepthook is original


def test_global_handler_chama_notificar_erro(mocker):
    spy_erro = mocker.patch("telemonit.excepthook.notificar.erro")
    spy_original = mocker.patch("sys.__excepthook__")

    try:
        raise ValueError("falha simulada")
    except ValueError:
        exc_type, exc_value, exc_tb = sys.exc_info()

    excepthook.global_handler(exc_type, exc_value, exc_tb)

    spy_erro.assert_called_once()
    kwargs = spy_erro.call_args.kwargs
    assert "ValueError" in kwargs["titulo"]
    assert "falha simulada" in kwargs["titulo"]
    assert kwargs["traceback"] is not None
    assert "ValueError" in kwargs["traceback"]
    spy_original.assert_called_once()


def test_global_handler_engole_falha_de_notificar(mocker):
    mocker.patch(
        "telemonit.excepthook.notificar.erro",
        side_effect=Exception("notificar quebrou"),
    )
    spy_original = mocker.patch("sys.__excepthook__")

    try:
        raise RuntimeError("x")
    except RuntimeError:
        exc_type, exc_value, exc_tb = sys.exc_info()

    # Não deve levantar mesmo com notificar.erro falhando
    excepthook.global_handler(exc_type, exc_value, exc_tb)
    spy_original.assert_called_once()
