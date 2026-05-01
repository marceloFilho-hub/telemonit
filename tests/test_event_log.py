"""Testes do event_log."""

from datetime import datetime, timezone

from telemonit import event_log


def test_append_event_sem_folder_id_retorna_false():
    assert event_log.append_event("", "proj", {"a": 1}) is False


def test_append_event_sem_projeto_retorna_false():
    assert event_log.append_event("folder123", "", {"a": 1}) is False


def test_nome_arquivo_segue_padrao():
    nome = event_log._nome_arquivo_mes("conciliador_prolabore")
    ano_mes = datetime.now(timezone.utc).strftime("%Y-%m")
    assert nome == f"eventos_conciliador_prolabore_{ano_mes}.jsonl"


def test_append_event_cria_arquivo_quando_nao_existe(mocker):
    fake_service = mocker.MagicMock()
    mocker.patch.object(event_log.drive_resolver, "_drive_service", return_value=fake_service)
    mocker.patch.object(event_log, "_buscar_arquivo", return_value=None)
    spy_criar = mocker.patch.object(event_log, "_criar_arquivo")
    spy_atualizar = mocker.patch.object(event_log, "_atualizar_arquivo")

    ok = event_log.append_event("folder123", "proj_x", {"nivel": "erro", "titulo": "t"})

    assert ok is True
    spy_criar.assert_called_once()
    spy_atualizar.assert_not_called()


def test_append_event_atualiza_arquivo_existente(mocker):
    fake_service = mocker.MagicMock()
    mocker.patch.object(event_log.drive_resolver, "_drive_service", return_value=fake_service)
    mocker.patch.object(event_log, "_buscar_arquivo", return_value="file_existente_id")
    mocker.patch.object(event_log, "_baixar_arquivo", return_value=b'{"ant":1}\n')
    spy_atualizar = mocker.patch.object(event_log, "_atualizar_arquivo")
    spy_criar = mocker.patch.object(event_log, "_criar_arquivo")

    ok = event_log.append_event("folder123", "proj_x", {"nivel": "info", "titulo": "novo"})

    assert ok is True
    spy_atualizar.assert_called_once()
    spy_criar.assert_not_called()
    args = spy_atualizar.call_args[0]
    conteudo_final = args[2]
    assert conteudo_final.startswith(b'{"ant":1}\n')
    assert b'"titulo": "novo"' in conteudo_final
    assert conteudo_final.endswith(b"\n")


def test_append_event_retorna_false_em_excecao(mocker):
    mocker.patch.object(
        event_log.drive_resolver,
        "_drive_service",
        side_effect=RuntimeError("SA não configurada"),
    )
    assert event_log.append_event("folder", "proj", {"x": 1}) is False
