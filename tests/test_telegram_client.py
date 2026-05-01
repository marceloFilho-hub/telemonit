"""Testes do telegram_client."""

from telemonit import telegram_client


def test_send_text_sem_token_retorna_false():
    assert telegram_client.send_text("", "123", "olá") is False


def test_send_text_sem_chat_id_retorna_false():
    assert telegram_client.send_text("token", "", "olá") is False


def test_send_text_sem_texto_retorna_false():
    assert telegram_client.send_text("token", "123", "") is False


def test_split_em_chunk_unico_quando_pequeno():
    chunks = telegram_client._split_in_chunks("texto curto", 4000)
    assert chunks == ["texto curto"]


def test_split_respeita_limite():
    texto = "a" * 9000
    chunks = telegram_client._split_in_chunks(texto, 4000)
    assert all(len(c) <= 4000 for c in chunks)
    assert "".join(chunks) == texto


def test_split_prefere_quebra_em_newline():
    texto = "linha1\n" + ("x" * 30) + "\nlinha3"
    chunks = telegram_client._split_in_chunks(texto, 20)
    # Deve quebrar em \n quando possível
    assert len(chunks) >= 2
    assert chunks[0].endswith("linha1") or "linha1" in chunks[0]


def test_send_text_envia_via_httpx(mocker):
    mock_post = mocker.patch("httpx.Client.post")
    mock_post.return_value.raise_for_status.return_value = None

    ok = telegram_client.send_text("TOKEN_X", "CHAT_Y", "ola mundo")

    assert ok is True
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert "TOKEN_X" in args[0]
    payload = kwargs["json"]
    assert payload["chat_id"] == "CHAT_Y"
    assert payload["text"] == "ola mundo"
    assert payload["parse_mode"] == "Markdown"


def test_send_text_falha_silenciosa_em_erro_de_rede(mocker):
    mocker.patch("httpx.Client.post", side_effect=Exception("connection reset"))
    assert telegram_client.send_text("TOKEN", "CHAT", "msg") is False
