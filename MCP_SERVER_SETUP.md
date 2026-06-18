# MCP Server Setup

Ten dokument jest przygotowany pod scenariusz:

- Garmin sync działa już na serwerze Linux
- FastAPI działa już na tym samym serwerze
- chcesz uruchomić lokalny MCP server, który czyta dane z FastAPI po `localhost`
- agent na serwerze ma używać MCP przez `stdio`

## Co już jest w repo

Lokalny MCP server:

- `app.mcp.server`

Najważniejsze narzędzia MCP:

- `healthcheck`
- `get_training_plan`
- `get_athlete_snapshot`
- `refresh_and_get_snapshot`
- `get_recent_activities`
- `get_activity_details`
- `get_readiness`
- `get_sleep_trends`
- `get_hrv_analysis`
- `generate_training_suggestion`
- `generate_daily_report`

## Jak działa architektura

```text
Garmin Connect
  ->
sync na Linuxie
  ->
baza danych
  ->
FastAPI na tym samym Linuxie
  ->
lokalny MCP server
  ->
agent uruchomiony na tym samym Linuxie
```

MCP server nie łączy się bezpośrednio z Garminem.
Łączy się z Twoim FastAPI po:

- `http://127.0.0.1:8000`

domyślnie i wysyła token API w nagłówku.

## Wymagane zmienne env

W `.env` na serwerze ustaw:

```env
AGENT_API_TOKEN=tu_wstaw_dlugi_losowy_token
AGENT_API_HEADER=X-Agent-Token
PUBLIC_HEALTHCHECK=true
CORS_ALLOW_ORIGINS=https://grucha.me,https://www.grucha.me

MCP_BACKEND_URL=http://127.0.0.1:8000
MCP_API_BASE_PATH=/api/v1
MCP_API_TOKEN=tu_wstaw_ten_sam_token_albo_osobny
MCP_REQUEST_TIMEOUT_SECONDS=30
```

Najprościej na start:

- `MCP_API_TOKEN = AGENT_API_TOKEN`

## Instalacja zależności

Na serwerze:

```bash
cd /opt/garmin-ai
.venv/bin/pip install -r requirements.txt
```

Jeśli nie używasz `venv`:

```bash
cd /opt/garmin-ai
python3 -m pip install -r requirements.txt
```

## Test backendu

Najpierw sprawdź FastAPI:

```bash
curl http://127.0.0.1:8000/health
```

Potem sprawdź endpoint chroniony:

```bash
curl \
  -H "X-Agent-Token: $AGENT_API_TOKEN" \
  http://127.0.0.1:8000/api/v1/athlete/training-plan
```

Jeśli to działa, MCP ma z czego czytać.

## Uruchomienie MCP ręcznie

Z `venv`:

```bash
cd /opt/garmin-ai
.venv/bin/python -m app.mcp.server
```

Bez `venv`:

```bash
cd /opt/garmin-ai
python3 -m app.mcp.server
```

To jest serwer `stdio`, więc zwykle nie uruchamia się go ręcznie “na stałe”.
Najczęściej startuje go sam klient MCP.

## Konfiguracja klienta MCP w Codex

Jeśli agent na serwerze używa Codex CLI / Codex App z lokalną konfiguracją MCP,
dodaj wpis do `~/.codex/config.toml`:

```toml
[mcp_servers.garmin_ai]
command = "/opt/garmin-ai/.venv/bin/python"
args = ["-m", "app.mcp.server"]
startup_timeout_sec = 30

[mcp_servers.garmin_ai.env]
MCP_BACKEND_URL = "http://127.0.0.1:8000"
MCP_API_BASE_PATH = "/api/v1"
MCP_API_TOKEN = "TU_WSTAW_TOKEN"
AGENT_API_HEADER = "X-Agent-Token"
```

Jeśli projekt stoi gdzie indziej niż `/opt/garmin-ai`, popraw ścieżki.

Po zmianie konfiguracji zwykle trzeba zrestartować klienta Codex albo otworzyć nową sesję.

## Konfiguracja klienta MCP w stylu JSON

Jeśli inny agent używa pliku JSON z sekcją `mcpServers`, odpowiednik wygląda tak:

```json
{
  "mcpServers": {
    "garmin-ai": {
      "command": "/opt/garmin-ai/.venv/bin/python",
      "args": ["-m", "app.mcp.server"],
      "env": {
        "MCP_BACKEND_URL": "http://127.0.0.1:8000",
        "MCP_API_BASE_PATH": "/api/v1",
        "MCP_API_TOKEN": "TU_WSTAW_TOKEN",
        "AGENT_API_HEADER": "X-Agent-Token"
      }
    }
  }
}
```

## Co agent powinien sprawdzić po podpięciu

1. Czy MCP server startuje bez błędu importu pakietu `mcp`.
2. Czy narzędzie `healthcheck` zwraca wynik z backendu.
3. Czy `get_training_plan` zwraca dane.
4. Czy `get_athlete_snapshot` działa bez `sync_live`.
5. Czy `refresh_and_get_snapshot` działa już z żywym syncem Garmin.

## Typowe problemy

### `Brakuje pakietu 'mcp'`

Zainstaluj zależności:

```bash
.venv/bin/pip install -r requirements.txt
```

### `401 Unauthorized`

Sprawdź:

- `AGENT_API_TOKEN` w FastAPI
- `MCP_API_TOKEN` w konfiguracji MCP
- `AGENT_API_HEADER`

### MCP działa, ale sync live nie działa

To zwykle oznacza problem po stronie:

- `.garmin_tokens/`
- logowania Garmin
- brakujących sekretów `GARMIN_EMAIL` / `GARMIN_PASSWORD`

### Agent nie widzi MCP tools

Sprawdź:

- czy klient MCP na pewno czyta odpowiedni config
- czy ścieżka do `python` jest poprawna
- czy uruchomiono nową sesję po dodaniu wpisu MCP

## Co dalej

Po pierwszym uruchomieniu warto dodać:

1. osobny write API do zapisu customowych tabel
2. narzędzia MCP do zapisu analiz pochodnych
3. osobne tabele Hyrox
4. ewentualnie osobną subdomenę publiczną tylko jeśli będziesz chciał zdalny MCP
