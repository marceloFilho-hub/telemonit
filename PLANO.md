# Plano — Sistema de Notificações Centralizado

> **⏸ Pausa noturna**: este plano foi finalizado em 2026-04-29 à noite e cópia salva em `Documents/automacoes/monitor_centralizado/PLANO.md` para o Marcelo retomar amanhã. Decisões abaixo já incluem os ajustes da última conversa (nome da lib sem "bhub" + monitor periódico 3x/dia rodando na VM).

---

## Context

Hoje cada projeto do Marcelo (conciliador_prolabore, Hidra, cadastro_contribuinte, etc.) trata erros isoladamente. Quando um pipeline trava na VM, ninguém é avisado em tempo real, e não há visão consolidada de "como estão minhas automações". A tentativa anterior de usar GitHub Actions com secrets para alertar via Telegram bateu na restrição de transferência do conciliador para a empresa — secrets pessoais não podem ir junto.

**Solução**: criar uma biblioteca Python `telemonit` (em repo privado pessoal do Marcelo, fora da empresa) que qualquer projeto importa para enviar notificações de erro/alerta. A biblioteca segue o padrão `drive:<file_id>` que o conciliador já usa: o `.env` do projeto cliente carrega só IDs do Drive, e a lib resolve via Service Account em runtime. Eventos são gravados em JSONL no Drive (canal de auditoria) e enviados em tempo real via Telegram (canal de alerta).

Adicionalmente, um script `monitor_periodico.py` da própria lib roda **3 vezes por dia na VM via Windows Task Scheduler** (cadência decidida pelo Marcelo), consolida os eventos da janela, e manda um resumo via Telegram. Isso elimina qualquer necessidade de secrets em git e mantém todo o stack na VM.

**Resultado pretendido:**
1. Real-time: pipeline travou na VM → mensagem na Donna em <30s
2. Resumo: 3x/dia (sugerido: 09h / 13h / 17h BRT) → resumo por janela com top erros por projeto
3. Audit trail permanente em JSONL no Drive
4. Onboarding de projeto novo em <5min via skill `/setup-messenger`

---

## Decisões já tomadas

- **Nome da lib**: `telemonit` (curto, fácil de importar — `from telemonit import notificar`).
- **Storage de eventos**: Pasta no Drive, JSONL particionado por projeto + mês (`eventos_{projeto}_{YYYY-MM}.jsonl`)
- **Bot Telegram**: Donna existente (token e chat_id já configurados em `claude-config/bots/.env`)
- **Repo da lib**: Privado pessoal — `marceloFilho-hub/telemonit`
- **Onde roda o monitor periódico**: VM, via **Windows Task Scheduler** (3x/dia). **Não** GitHub Actions. Motivo: cadência alta (2-3x/dia) torna VM mais econômica e fica tudo num lugar só.
- **Credenciais**: 100% via `drive:<file_id>` resolvido pelo SA da VM. **Zero secrets no GitHub.**

---

## Arquitetura

```
┌────────────────────────────────────────────────────────────────┐
│  VM (sempre ligada)                                            │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │ Projetos clientes                                        │ │
│  │                                                          │ │
│  │ conciliador_prolabore                                    │ │
│  │   ├── vendor/telemonit/   ← cópia da lib              │ │
│  │   └── em erro:                                          │ │
│  │       ├── HTTP POST → api.telegram.org (real-time)     │ │
│  │       └── append → Drive: eventos_*.jsonl              │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │ Windows Task Scheduler                                   │ │
│  │   monitor_periodico.py (3x/dia: 09h, 13h, 17h BRT)      │ │
│  │     └── lê cursor + eventos novos                       │ │
│  │          └── gera resumo                                │ │
│  │               └── HTTP POST → api.telegram.org          │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                                │
│  Credenciais: SA Drive já existe na VM, .env tem só drive:IDs │
└────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌────────────────────────────────────────────────────────────────┐
│  Pasta no Drive (DRIVE_PASTA_MONITOR_LOG_ID)                  │
│                                                                │
│  eventos_conciliador_prolabore_2026-04.jsonl                  │
│  eventos_hidra_2026-04.jsonl                                  │
│  eventos_cadastro_contribuinte_2026-04.jsonl                  │
│  cursor_resumo_periodico.json                                 │
└────────────────────────────────────────────────────────────────┘
```

> **Nada vai pra GitHub Actions / secrets.** Toda comunicação Telegram parte da VM, com credenciais resolvidas via SA local.

---

## Repo `telemonit` — estrutura

```
marceloFilho-hub/telemonit  (privado pessoal)
├── pyproject.toml
├── README.md
├── .env.example
├── .gitignore
├── telemonit/
│   ├── __init__.py            # exporta API pública
│   ├── notificar.py           # API pública: erro(), alerta(), info()
│   ├── telegram_client.py     # httpx — envia mensagem (REUSA padrão de telegram_msg/bots/base.py)
│   ├── drive_resolver.py      # resolve drive:<file_id> via SA (extraído de conciliador/email_monitor.py:115-156)
│   ├── event_log.py           # append-style writer no JSONL Drive
│   ├── throttle.py            # dedup local em memória + arquivo (storm protection)
│   └── excepthook.py          # global_handler para sys.excepthook
├── scripts/
│   ├── monitor_periodico.py   # entry point chamado pelo Windows Task Scheduler
│   ├── setup_messenger.py     # configura um projeto cliente (CLI)
│   └── instalar_task_scheduler.ps1  # cria as 3 tarefas agendadas no Windows
└── tests/
    ├── test_telegram_client.py
    ├── test_drive_resolver.py
    └── test_throttle.py
```

---

## API pública da lib

```python
from telemonit import notificar

notificar.erro(
    titulo="Pipeline travou em CARNEVALE",
    detalhes="APIError [429] Quota Sheets exceeded",
    traceback=tb,
    contexto={"origem": "CARNEVALE", "competencia": "04/2026"},
)

notificar.alerta(titulo="Quota Sheets API alta", detalhes="...")
notificar.info(titulo="Pipeline concluído", detalhes="X empresas OK")
```

Behavior:
- `erro` sempre dispara Telegram + grava JSONL
- `alerta` dispara Telegram + grava JSONL, **com throttle** (mesmo título em <5 min ⇒ engole)
- `info` apenas grava JSONL (Telegram só se `MONITOR_NIVEL=info`)

---

## Variáveis `.env` do projeto cliente

```ini
# telemonit
MONITOR_PROJETO=conciliador_prolabore
MONITOR_TG_TOKEN=drive:<file_id_do_token_donna>
MONITOR_TG_CHAT_ID=drive:<file_id_do_chat_id>
MONITOR_DRIVE_LOG_FOLDER=<id_da_pasta_de_logs>
MONITOR_NIVEL=alerta              # info | alerta | erro (default: alerta)
GOOGLE_APPLICATION_CREDENTIALS=credentials/gdrive_service_account.json
```

---

## Reaproveitamento de código existente

| Componente | Onde existe hoje | Como será reaproveitado |
|---|---|---|
| Envio Telegram (httpx + Markdown + chunking) | `automacoes/telegram_msg/bots/base.py:101-121` (`send_text`) | Replicado em `telegram_client.py` (versão sync) |
| Resolução `drive:<file_id>` | `conciliador_prolabore/src/monitor/email_monitor.py:115-156` (`_resolver_secrets_drive`) | Extraído e generalizado em `drive_resolver.py` |
| Padrão JSONL no Drive | `conciliador_prolabore/src/monitor/historico_remoto.py` + `processados_remoto.py` | `event_log.py` segue o mesmo padrão |
| Service Account / build_service Drive | `conciliador_prolabore/src/drive/drive_client.py` | Replicado em `drive_resolver.py` (módulo standalone) |
| TelegramAlerter pattern | `automacoes/control_panel/src/observability/alerter.py` | Inspiração de design |

---

## Fases de execução

### Fase 1 — Lib MVP no repo novo
1. Decidir nome da lib com Marcelo
2. `gh repo create marceloFilho-hub/telemonit --private`
3. Implementar módulos da lib (notificar, telegram_client, drive_resolver, event_log, throttle, excepthook)
4. `pyproject.toml` com deps mínimas (`httpx`, `google-api-python-client`, `python-dotenv`)
5. Testes cobrindo throttle, drive_resolver, telegram_client (com mocks)
6. README com instruções de instalação

### Fase 2 — Adoção no `conciliador_prolabore` (vendor)
1. Branch `feat/telemonit-integration` no conciliador
2. Vendorar: copiar `telemonit/` da lib para `vendor/telemonit/` no conciliador
3. Subir token Donna + chat_id para o Drive (mesmo padrão dos outros `drive:<id>` do conciliador)
4. Criar pasta de logs no Drive (1 pasta única para todos os projetos)
5. Atualizar `.env.example` + `.env` com as 5 variáveis novas
6. Hook em `logica/conciliador.py` e `src/monitor/email_monitor.py::_verificar_uma_vez`:
   - `sys.excepthook = telemonit.global_handler`
   - try/except no loop principal chamando `notificar.erro` em falhas
7. Atualizar README do conciliador com seção "Notificações"
8. PR

### Fase 3 — Monitor periódico via Windows Task Scheduler na VM
1. `scripts/monitor_periodico.py` (no repo da lib):
   - Carregar `.env` da VM (mesmo SA + IDs Drive)
   - Ler `cursor_resumo_periodico.json` do Drive
   - Listar todos `eventos_*.jsonl` da pasta de logs
   - Filtrar eventos com timestamp > cursor
   - Agregar por projeto + nível (top 5 erros)
   - Formatar mensagem Markdown
   - HTTP POST Telegram (Donna)
   - Atualizar cursor
2. `scripts/instalar_task_scheduler.ps1`:
   - Cria 3 tarefas agendadas (`schtasks /create`):
     - `MonitorPeriodico_Manha` (09:00 BRT)
     - `MonitorPeriodico_Tarde` (13:00 BRT)
     - `MonitorPeriodico_Noite` (17:00 BRT)
   - Cada uma chama `pythonw.exe scripts\monitor_periodico.py`
3. Testar manualmente: rodar o script direto + checar Telegram + cursor atualizado
4. Documentar comandos de gestão no README:
   - `schtasks /query /tn MonitorPeriodico_*` para listar
   - `schtasks /run /tn MonitorPeriodico_Manha` para disparo manual

### Fase 4 — Skill `/setup-messenger` (Claude Code)
1. Skill em `~/.claude/skills/setup-messenger/SKILL.md`
2. Automação:
   - Vendora a lib (cópia da pasta)
   - Adiciona variáveis `.env.example`
   - Insere hook no entry point detectado (main.py / app.py / conciliador.py / etc.)
   - Atualiza README
   - Branch + commit + PR
3. Documentação de invocação: `/setup-messenger`

---

## Arquivos a criar

### No repo novo `telemonit`
- `pyproject.toml`
- `README.md`
- `.env.example`
- `.gitignore`
- `telemonit/__init__.py`
- `telemonit/notificar.py`
- `telemonit/telegram_client.py`
- `telemonit/drive_resolver.py`
- `telemonit/event_log.py`
- `telemonit/throttle.py`
- `telemonit/excepthook.py`
- `scripts/monitor_periodico.py`
- `scripts/setup_messenger.py`
- `scripts/instalar_task_scheduler.ps1`
- `tests/test_telegram_client.py`
- `tests/test_drive_resolver.py`
- `tests/test_throttle.py`

### No `conciliador_prolabore` (Fase 2)
- `vendor/telemonit/` (cópia da lib)
- `.env.example` — adicionar 5 variáveis
- `logica/conciliador.py` — hook excepthook
- `src/monitor/email_monitor.py` — try/except no loop com `notificar.erro`
- `README.md` — seção "Notificações"

### Skill local (Fase 4)
- `~/.claude/skills/setup-messenger/SKILL.md`

---

## Verificação end-to-end

### Fase 1 (lib MVP)
```bash
cd ~/Documents/dev/telemonit
uv venv && source .venv/Scripts/activate
uv pip install -e .
pytest tests/ -v
python -c "from telemonit import notificar; notificar.info(titulo='teste', detalhes='funcionou')"
# → mensagem chega na Donna + linha no JSONL no Drive
```

### Fase 2 (conciliador integrado)
```bash
cd ~/Documents/automacoes/conciliador_prolabore
PYTHONUTF8=1 .venv/Scripts/python.exe -c "
import sys; sys.path.insert(0, 'vendor')
from telemonit import notificar
notificar.erro(titulo='Teste de erro', detalhes='disparado manualmente')
"
# (a) Donna recebeu mensagem em <10s
# (b) eventos_conciliador_prolabore_2026-04.jsonl no Drive ganhou linha nova
```

### Fase 3 (monitor periódico)
```powershell
# Disparar manualmente (sem esperar 09h)
schtasks /run /tn MonitorPeriodico_Manha
# → Donna recebe resumo da janela
# → cursor_resumo_periodico.json no Drive atualizado

# Listar status das 3 tarefas
schtasks /query /tn MonitorPeriodico_Manha /v /fo LIST
schtasks /query /tn MonitorPeriodico_Tarde /v /fo LIST
schtasks /query /tn MonitorPeriodico_Noite /v /fo LIST
```

### Fase 4 (skill)
```bash
cd ~/Documents/automacoes/Hidra
/setup-messenger
# → branch nova, vendor/ adicionado, .env.example atualizado, hook inserido, PR aberto
```

---

## Riscos e mitigações

| Risco | Mitigação |
|---|---|
| Vendor desatualiza nos clientes | Skill `/atualizar-messenger` em fase futura para sync; ou checagem de versão no startup |
| Loop de erro chama notificar→quebra→loop | Throttle global + try/except interno na própria lib (silenciosa em última instância) |
| VM offline na hora de uma tarefa agendada | Windows Task Scheduler tem flag "executar quando voltar" — habilitar `/RU SYSTEM /RL HIGHEST /SC DAILY /MO 1` com `/RUN_LATEST` |
| Drive offline / quota 429 no append | Buffer local em arquivo, retry no próximo evento; lib nunca lança exceção pro caller |
| Concorrência de escrita no JSONL | Particionamento por projeto + mês evita overlap (1 projeto = 1 escritor por arquivo) |
| Atualização da Donna afeta projetos da empresa | Vendor (versão congelada por projeto) — lib nova só entra em projeto novo via skill |
| `.env` da VM perdido em reinstalação | Padrão `drive:<file_id>` já protege — só o SA precisa estar em `credentials/` |

---

## O que decidir amanhã (2 itens)

1. **Cadência exata do periódico**: 09h/13h/17h BRT? Ou outras 2-3 janelas?
2. **Pasta no Drive** para os logs centralizados — criar nova pasta agora, ou reaproveitar `1KLH6jWmzDtBVoFj34KzbwNdIkl8hZRgg` (a do histórico do conciliador) com subpasta `logs/`?

Após decidir esses 2 pontos, executar Fase 1 → 2 → 3 → 4 em sessões separadas.
