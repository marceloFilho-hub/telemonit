# telemonit

Biblioteca de notificações centralizadas para automações do Marcelo.

Envia alertas em tempo real via Telegram (bot Donna) e grava trilha de auditoria em JSONL no Google Drive. Inclui um monitor periódico que roda na VM via Windows Task Scheduler para gerar resumos consolidados.

## Visão geral

- **Real-time**: pipeline travou → mensagem na Donna em <30s
- **Resumo periódico**: 3x/dia (09h / 13h / 17h BRT) consolida eventos por projeto
- **Audit trail**: eventos persistidos em JSONL particionado por projeto + mês no Drive
- **Zero secrets em git**: todas as credenciais resolvidas via padrão `drive:<file_id>` com Service Account local na VM

## Estrutura

```
telemonit/
├── telemonit/            # Pacote da lib
│   ├── __init__.py       # API pública
│   ├── notificar.py      # erro() / alerta() / info()
│   ├── telegram_client.py
│   ├── drive_resolver.py
│   ├── event_log.py
│   ├── throttle.py
│   └── excepthook.py
├── scripts/
│   ├── monitor_periodico.py
│   ├── setup_messenger.py
│   └── instalar_task_scheduler.ps1
└── tests/
```

## Instalação (desenvolvimento)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

## Uso básico

```python
from telemonit import notificar

notificar.erro(
    titulo="Pipeline travou em CARNEVALE",
    detalhes="APIError [429] Quota Sheets exceeded",
    contexto={"origem": "CARNEVALE", "competencia": "04/2026"},
)
```

## Variáveis de ambiente

Ver [.env.example](.env.example).

| Variável | Descrição |
|---|---|
| `MONITOR_PROJETO` | Identificador do projeto cliente |
| `MONITOR_TG_TOKEN` | Token do bot Telegram (formato `drive:<file_id>`) |
| `MONITOR_TG_CHAT_ID` | Chat ID do destino (formato `drive:<file_id>`) |
| `MONITOR_DRIVE_LOG_FOLDER` | ID da pasta do Drive onde os JSONL são gravados |
| `MONITOR_NIVEL` | `info` \| `alerta` \| `erro` (default: `alerta`) |
| `GOOGLE_APPLICATION_CREDENTIALS` | Caminho para o JSON da Service Account |

## Status

Em construção — Fase 1 (MVP da lib). Ver [PLANO.md](PLANO.md) para o roadmap completo.
