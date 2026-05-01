"""Throttle de notificações — dedup por chave com TTL.

Storm protection: se a mesma chave (titulo+nivel+projeto) for emitida
em um intervalo menor que o TTL, a segunda chamada é engolida.

Persiste estado em arquivo no diretório temporário do SO para sobreviver
a reinícios curtos de processo.
"""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

TTL_PADRAO_SEGUNDOS = 300  # 5 minutos
_STATE_PATH = Path(tempfile.gettempdir()) / "telemonit_throttle.json"
_memoria: dict[str, float] = {}
_carregado = False


def _carregar() -> None:
    """Carrega estado persistido para a memória (uma vez por processo)."""
    global _carregado
    if _carregado:
        return
    _carregado = True
    try:
        if _STATE_PATH.exists():
            with _STATE_PATH.open("r", encoding="utf-8") as f:
                dados = json.load(f)
                _memoria.update({str(k): float(v) for k, v in dados.items()})
    except Exception:
        # Estado corrompido — recomeça vazio
        _memoria.clear()


def _persistir() -> None:
    """Persiste o estado atual em disco (best-effort, ignora falhas)."""
    try:
        with _STATE_PATH.open("w", encoding="utf-8") as f:
            json.dump(_memoria, f)
    except Exception:
        pass


def _expirar(ttl: int) -> None:
    """Remove entradas mais antigas que ttl."""
    agora = time.time()
    expiradas = [k for k, t in _memoria.items() if agora - t > ttl]
    for k in expiradas:
        _memoria.pop(k, None)


def deve_emitir(chave: str, ttl: int = TTL_PADRAO_SEGUNDOS) -> bool:
    """Retorna True se a chave pode emitir (e marca emissão); False se está em throttle."""
    _carregar()
    _expirar(ttl)

    agora = time.time()
    ultimo = _memoria.get(chave)
    if ultimo is not None and agora - ultimo < ttl:
        return False

    _memoria[chave] = agora
    _persistir()
    return True


def reset() -> None:
    """Limpa estado (útil para testes)."""
    global _carregado
    _memoria.clear()
    _carregado = False
    try:
        if _STATE_PATH.exists():
            _STATE_PATH.unlink()
    except Exception:
        pass
