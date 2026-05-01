"""Testes do drive_resolver."""

from telemonit import drive_resolver


def test_valor_none_retorna_none():
    assert drive_resolver.resolver(None) is None


def test_valor_sem_prefixo_drive_passa_pelo_filtro():
    assert drive_resolver.resolver("token-puro-123") == "token-puro-123"


def test_valor_string_vazia_passa():
    assert drive_resolver.resolver("") == ""


def test_drive_prefix_chama_baixar(monkeypatch):
    chamadas = []

    def fake_baixar(file_id):
        chamadas.append(file_id)
        return "conteudo-do-drive"

    monkeypatch.setattr(drive_resolver, "_baixar_conteudo", fake_baixar)

    resultado = drive_resolver.resolver("drive:abc123")

    assert resultado == "conteudo-do-drive"
    assert chamadas == ["abc123"]


def test_drive_prefix_com_id_vazio_retorna_vazio(monkeypatch):
    """`drive:` sem id não deve quebrar — retorna string vazia."""
    monkeypatch.setattr(drive_resolver, "_baixar_conteudo", lambda _: "deveria-nao-chamar")
    assert drive_resolver.resolver("drive:") == ""
    assert drive_resolver.resolver("drive:   ") == ""


def test_drive_prefix_strip_espacos(monkeypatch):
    capturado = {}

    def fake_baixar(file_id):
        capturado["id"] = file_id
        return "ok"

    monkeypatch.setattr(drive_resolver, "_baixar_conteudo", fake_baixar)
    drive_resolver.resolver("drive:  fileXYZ  ")
    assert capturado["id"] == "fileXYZ"
