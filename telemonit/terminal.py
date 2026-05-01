"""Captura stdout/stderr e dispara `notificar.erro` automaticamente em exceções.

Pensado para wrappers de rodadas — útil para o `control_panel` ou qualquer
script que queira reportar falhas com traceback + saída do terminal incluídos.

Uso:
    from telemonit import capturar_terminal

    with capturar_terminal(run_id="run-2026-05-01-001"):
        executar_pipeline()  # se levantar exceção, notificar.erro é chamado

A saída original do terminal é preservada (tee): stdout/stderr continuam
sendo escritos no console do processo.
"""

from __future__ import annotations

import contextlib
import io
import sys
import traceback as tb_module
from typing import Iterator

from . import notificar

_LIMITE_STDOUT_CHARS = 1000
_LIMITE_STDERR_CHARS = 2000


class _Tee:
    """Encaminha writes para múltiplos streams (terminal + buffer)."""

    def __init__(self, *streams) -> None:
        self._streams = streams

    def write(self, data) -> int:
        n = 0
        for stream in self._streams:
            try:
                stream.write(data)
                n = len(data) if isinstance(data, str) else 0
            except Exception:
                pass
        return n

    def flush(self) -> None:
        for stream in self._streams:
            try:
                stream.flush()
            except Exception:
                pass

    def isatty(self) -> bool:
        for stream in self._streams:
            try:
                if stream.isatty():
                    return True
            except Exception:
                continue
        return False

    def __getattr__(self, name):
        # Delega atributos não cobertos para o primeiro stream (terminal real).
        return getattr(self._streams[0], name)


@contextlib.contextmanager
def capturar_terminal(
    run_id: str | None = None,
    *,
    titulo_erro: str = "Falha durante execução",
    incluir_saida: bool = True,
) -> Iterator[None]:
    """Context manager que captura stdout/stderr e reporta exceções.

    Args:
        run_id: identificador da rodada — vai como campo first-class no evento
            e no throttle. Recomendado quando há controle de execuções.
        titulo_erro: título da notificação em caso de exceção.
        incluir_saida: se True (default), inclui as últimas linhas de
            stdout/stderr capturadas em `detalhes` da notificação.

    Comportamento:
        - Em exceção: chama `notificar.erro` e **re-levanta** a exceção
          (a lib não engole — quem chama precisa decidir se aborta).
        - Em saída normal: nada é enviado.
        - O terminal continua recebendo as mensagens (tee).
    """
    buffer_out = io.StringIO()
    buffer_err = io.StringIO()

    stdout_orig = sys.stdout
    stderr_orig = sys.stderr
    sys.stdout = _Tee(stdout_orig, buffer_out)
    sys.stderr = _Tee(stderr_orig, buffer_err)

    try:
        yield
    except BaseException as exc:
        sys.stdout = stdout_orig
        sys.stderr = stderr_orig
        try:
            tb_str = tb_module.format_exc()
            partes_detalhes = [str(exc) or exc.__class__.__name__]

            if incluir_saida:
                err_capturado = buffer_err.getvalue()
                out_capturado = buffer_out.getvalue()
                if err_capturado:
                    partes_detalhes.append(
                        "\n[stderr final]\n" + err_capturado[-_LIMITE_STDERR_CHARS:]
                    )
                if out_capturado:
                    partes_detalhes.append(
                        "\n[stdout final]\n" + out_capturado[-_LIMITE_STDOUT_CHARS:]
                    )

            notificar.erro(
                titulo=titulo_erro,
                detalhes="\n".join(partes_detalhes),
                traceback=tb_str,
                run_id=run_id,
            )
        except Exception:
            # Lib nunca quebra o caller, nem dentro do handler de erro.
            pass
        raise
    finally:
        sys.stdout = stdout_orig
        sys.stderr = stderr_orig
