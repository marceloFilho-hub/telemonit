"""Testes da configuração programática."""

import pytest

import telemonit
from telemonit import config


_VARS_ENV = (
    "MONITOR_PROJETO",
    "MONITOR_TG_TOKEN",
    "MONITOR_TG_CHAT_ID",
    "MONITOR_DRIVE_LOG_FOLDER",
    "MONITOR_NIVEL",
)


@pytest.fixture(autouse=True)
def _ambiente_limpo(monkeypatch):
    """Garante teste isolado: zera config programática e env vars."""
    config.resetar()
    for var in _VARS_ENV:
        monkeypatch.delenv(var, raising=False)
    yield
    config.resetar()


def test_default_quando_nada_configurado():
    cfg = config.obter()
    assert cfg["projeto"] == "desconhecido"
    assert cfg["tg_token_raw"] == ""
    assert cfg["tg_chat_id_raw"] == ""
    assert cfg["drive_folder"] == ""
    assert cfg["nivel_minimo"] == "alerta"


def test_env_var_e_lida(monkeypatch):
    monkeypatch.setenv("MONITOR_PROJETO", "do_env")
    monkeypatch.setenv("MONITOR_NIVEL", "INFO")
    cfg = config.obter()
    assert cfg["projeto"] == "do_env"
    assert cfg["nivel_minimo"] == "info"  # normaliza para minúsculas


def test_configurar_sobrescreve_env(monkeypatch):
    monkeypatch.setenv("MONITOR_PROJETO", "do_env")
    telemonit.configurar(projeto="programatico")
    cfg = config.obter()
    assert cfg["projeto"] == "programatico"


def test_configurar_todos_os_parametros():
    telemonit.configurar(
        projeto="proj",
        telegram_token="tok",
        telegram_chat_id="chat",
        drive_folder="folder",
        nivel="info",
    )
    cfg = config.obter()
    assert cfg["projeto"] == "proj"
    assert cfg["tg_token_raw"] == "tok"
    assert cfg["tg_chat_id_raw"] == "chat"
    assert cfg["drive_folder"] == "folder"
    assert cfg["nivel_minimo"] == "info"


def test_configurar_chamadas_sucessivas_atualizam_apenas_passados():
    telemonit.configurar(projeto="A", telegram_token="T1")
    telemonit.configurar(telegram_token="T2")  # mantém projeto, atualiza só token
    cfg = config.obter()
    assert cfg["projeto"] == "A"
    assert cfg["tg_token_raw"] == "T2"


def test_configurar_parametro_desconhecido_levanta():
    with pytest.raises(TypeError):
        telemonit.configurar(parametro_inexistente="x")


def test_configurar_aceita_apenas_kwargs():
    with pytest.raises(TypeError):
        telemonit.configurar("posicional")  # type: ignore[misc]


def test_resetar_zera_estado():
    telemonit.configurar(projeto="X")
    config.resetar()
    cfg = config.obter()
    assert cfg["projeto"] == "desconhecido"


def test_atalhos_top_level_sao_callable():
    assert callable(telemonit.erro)
    assert callable(telemonit.alerta)
    assert callable(telemonit.info)
    assert callable(telemonit.configurar)


def test_atalho_top_level_funciona_como_notificar(mocker):
    """telemonit.erro() deve ser o mesmo objeto que telemonit.notificar.erro."""
    assert telemonit.erro is telemonit.notificar.erro
    assert telemonit.alerta is telemonit.notificar.alerta
    assert telemonit.info is telemonit.notificar.info
