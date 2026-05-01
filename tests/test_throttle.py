"""Testes do throttle."""

import time

import pytest

from telemonit import throttle


@pytest.fixture(autouse=True)
def isolar_estado(tmp_path, monkeypatch):
    """Isola arquivo de estado e memória em cada teste."""
    state_file = tmp_path / "throttle.json"
    monkeypatch.setattr(throttle, "_STATE_PATH", state_file)
    throttle._memoria.clear()
    throttle._carregado = False
    yield
    throttle._memoria.clear()
    throttle._carregado = False


def test_primeira_emissao_passa():
    assert throttle.deve_emitir("k1", ttl=60) is True


def test_segunda_emissao_dentro_do_ttl_bloqueia():
    assert throttle.deve_emitir("k1", ttl=60) is True
    assert throttle.deve_emitir("k1", ttl=60) is False


def test_emissao_apos_ttl_passa():
    assert throttle.deve_emitir("k2", ttl=1) is True
    time.sleep(1.1)
    assert throttle.deve_emitir("k2", ttl=1) is True


def test_chaves_diferentes_nao_se_bloqueiam():
    assert throttle.deve_emitir("a", ttl=60) is True
    assert throttle.deve_emitir("b", ttl=60) is True
    assert throttle.deve_emitir("a", ttl=60) is False
    assert throttle.deve_emitir("b", ttl=60) is False


def test_persistencia_entre_carregamentos(tmp_path, monkeypatch):
    state_file = tmp_path / "persist.json"
    monkeypatch.setattr(throttle, "_STATE_PATH", state_file)
    throttle._memoria.clear()
    throttle._carregado = False

    assert throttle.deve_emitir("persist-k", ttl=60) is True

    # Simula novo processo: limpa memória mas mantém arquivo
    throttle._memoria.clear()
    throttle._carregado = False

    assert throttle.deve_emitir("persist-k", ttl=60) is False
