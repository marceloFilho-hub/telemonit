# telemonit

Biblioteca de notificações centralizadas para automações do Marcelo.

Envia alertas em tempo real via Telegram (bot Donna) e grava trilha de auditoria em JSONL no Google Drive. Inclui um monitor periódico que roda na VM via Windows Task Scheduler para gerar resumos consolidados.

## Visão geral

- **Real-time**: pipeline travou → mensagem na Donna em <30s
- **Resumo periódico**: 3x/dia (09h / 13h / 17h BRT) consolida eventos por projeto
- **Audit trail**: eventos persistidos em JSONL particionado por projeto + mês no Drive
- **Zero secrets em git**: credenciais resolvidas via padrão `drive:<file_id>` com Service Account local

## Estrutura

```
telemonit/
├── telemonit/            # Pacote da lib
│   ├── __init__.py       # API pública (configurar / erro / alerta / info)
│   ├── config.py         # configuração programática
│   ├── notificar.py      # erro() / alerta() / info()
│   ├── telegram_client.py
│   ├── drive_resolver.py
│   ├── event_log.py
│   ├── throttle.py
│   └── excepthook.py
├── scripts/              # entry points do monitor periódico (Fase 3)
└── tests/
```

## Instalação

A `telemonit` se comporta como qualquer lib Python (pandas, numpy): você instala uma vez e importa em qualquer projeto.

### 1. Como dependência de outro projeto (recomendado)

```powershell
pip install git+https://github.com/marceloFilho-hub/telemonit.git
```

Ou no `requirements.txt` do projeto cliente:

```
telemonit @ git+https://github.com/marceloFilho-hub/telemonit.git@main
```

> Repo é privado: o pip da máquina precisa estar autenticado no GitHub (`gh auth login` ou PAT no `~/.gitconfig`).

### 2. Vendoring (cópia da pasta)

Para projetos que **não podem depender de repo pessoal** (ex.: o `conciliador_prolabore`, que vai migrar para a empresa):

```powershell
# da raiz do projeto cliente
Copy-Item -Recurse C:\caminho\para\telemonit\telemonit .\vendor\telemonit
```

E no entry point do projeto cliente:

```python
import sys
sys.path.insert(0, "vendor")
import telemonit
```

### 3. Modo desenvolvimento (no próprio repo)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

## Uso

### Configuração programática (estilo `pd.set_option`)

```python
import telemonit

telemonit.configurar(
    projeto="conciliador_prolabore",
    telegram_token="drive:1abc...xyz",
    telegram_chat_id="drive:1def...uvw",
    drive_folder="folder_id_dos_logs",
    nivel="alerta",   # info | alerta | erro
)

# Atalhos top-level (estilo pd.read_csv, np.array):
telemonit.erro(
    titulo="Pipeline travou em CARNEVALE",
    detalhes="APIError [429] Quota Sheets exceeded",
    contexto={"empresa": "ACME", "competencia": "04/2026"},
)

telemonit.alerta(titulo="Quota Sheets API alta")
telemonit.info(titulo="Pipeline concluído", detalhes="42 empresas OK")
```

### Configuração via `.env` (alternativa)

Crie um `.env` na raiz do projeto cliente — ver [.env.example](.env.example):

```ini
MONITOR_PROJETO=conciliador_prolabore
MONITOR_TG_TOKEN=drive:<file_id_do_token_donna>
MONITOR_TG_CHAT_ID=drive:<file_id_do_chat_id>
MONITOR_DRIVE_LOG_FOLDER=<id_da_pasta_de_logs>
MONITOR_NIVEL=alerta
GOOGLE_APPLICATION_CREDENTIALS=credentials/gdrive_service_account.json
```

E importe direto:

```python
from telemonit import notificar
notificar.erro(titulo="...", detalhes="...")
```

### Precedência de configuração

```
configurar() > variáveis de ambiente > defaults
```

Você pode misturar: deixar a maioria no `.env` e sobrescrever só o `projeto` ou o `nivel` em runtime via `configurar()`.

### Captura global de exceções

```python
from telemonit import excepthook

excepthook.instalar()  # qualquer exceção não tratada vira notificar.erro
```

## Comportamento das funções

| Função | Telegram | JSONL | Throttle |
|---|---|---|---|
| `erro` | sempre | sempre | não |
| `alerta` | sempre | sempre | 5 min por chave (titulo+projeto) |
| `info` | só se `nivel=info` | sempre | não |

A lib **nunca** propaga exceção para o caller — falhas internas são silenciosas para não derrubar o pipeline cliente.

## Variáveis de ambiente

| Variável | Descrição |
|---|---|
| `MONITOR_PROJETO` | Identificador do projeto cliente |
| `MONITOR_TG_TOKEN` | Token do bot Telegram (aceita `drive:<file_id>`) |
| `MONITOR_TG_CHAT_ID` | Chat ID do destino (aceita `drive:<file_id>`) |
| `MONITOR_DRIVE_LOG_FOLDER` | ID da pasta do Drive onde os JSONL são gravados |
| `MONITOR_NIVEL` | `info` \| `alerta` \| `erro` (default: `alerta`) |
| `GOOGLE_APPLICATION_CREDENTIALS` | Caminho para o JSON da Service Account |

## Testes

```powershell
.\.venv\Scripts\Activate.ps1
python -m pytest tests/ -v
```

## Roadmap

Ver [PLANO.md](PLANO.md). Fase 1 (MVP) concluída — próximas etapas: Fase 2 (vendoring no `conciliador_prolabore`), Fase 3 (`monitor_periodico.py` na VM via Task Scheduler), Fase 4 (skill `/setup-messenger`).
