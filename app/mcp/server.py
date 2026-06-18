"""Lokalny MCP server dla Garmin AI.

Serwer działa jako adapter nad istniejącym FastAPI i wystawia narzędzia
do odczytu kontekstu sportowego oraz generowania sugestii treningowych.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Optional

import requests
from dotenv import load_dotenv

load_dotenv()

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:  # pragma: no cover - zależne od środowiska wdrożeniowego
    FastMCP = None


@dataclass(frozen=True)
class BackendConfig:
    """Konfiguracja połączenia MCP -> FastAPI."""

    backend_url: str
    api_base_path: str
    api_token: str
    token_header: str
    timeout_seconds: float

    @property
    def api_root(self) -> str:
        return f"{self.backend_url.rstrip('/')}{self.api_base_path}"


@dataclass(frozen=True)
class RuntimeConfig:
    """Konfiguracja uruchomienia MCP servera."""

    transport: str
    host: str
    port: int
    streamable_http_path: str
    mount_path: Optional[str]


def load_backend_config() -> BackendConfig:
    """Ładuje konfigurację backendu z env."""
    backend_url = os.getenv("MCP_BACKEND_URL", "http://127.0.0.1:8000").strip()
    api_base_path = os.getenv("MCP_API_BASE_PATH", "/api/v1").strip() or "/api/v1"
    api_token = (
        os.getenv("MCP_API_TOKEN")
        or os.getenv("AGENT_API_TOKEN")
        or ""
    ).strip()
    token_header = os.getenv("AGENT_API_HEADER", "X-Agent-Token").strip() or "X-Agent-Token"
    timeout_seconds = float(os.getenv("MCP_REQUEST_TIMEOUT_SECONDS", "30").strip() or "30")

    return BackendConfig(
        backend_url=backend_url,
        api_base_path=api_base_path if api_base_path.startswith("/") else f"/{api_base_path}",
        api_token=api_token,
        token_header=token_header,
        timeout_seconds=timeout_seconds,
    )


def load_runtime_config() -> RuntimeConfig:
    """Ładuje konfigurację transportu MCP z env."""
    transport = (os.getenv("MCP_TRANSPORT", "stdio") or "stdio").strip().lower()
    allowed_transports = {"stdio", "sse", "streamable-http"}
    if transport not in allowed_transports:
        raise ValueError(
            f"Nieobsługiwany MCP_TRANSPORT='{transport}'. Dozwolone: {sorted(allowed_transports)}"
        )

    host = (os.getenv("MCP_SERVER_HOST", "127.0.0.1") or "127.0.0.1").strip()
    port = int((os.getenv("MCP_SERVER_PORT", "8001") or "8001").strip())

    streamable_http_path = (
        os.getenv("MCP_STREAMABLE_HTTP_PATH", "/mcp") or "/mcp"
    ).strip()
    if not streamable_http_path.startswith("/"):
        streamable_http_path = f"/{streamable_http_path}"

    mount_path_env = (os.getenv("MCP_MOUNT_PATH") or "").strip()
    mount_path = mount_path_env or None
    if mount_path and not mount_path.startswith("/"):
        mount_path = f"/{mount_path}"

    return RuntimeConfig(
        transport=transport,
        host=host,
        port=port,
        streamable_http_path=streamable_http_path,
        mount_path=mount_path,
    )


def build_session(config: BackendConfig) -> requests.Session:
    """Tworzy sesję HTTP do komunikacji z backendem."""
    session = requests.Session()
    session.headers.update(
        {
            "Accept": "application/json",
            "User-Agent": "garmin-ai-mcp/0.1",
        }
    )
    if config.api_token:
        session.headers[config.token_header] = config.api_token
    return session


def request_json(
    session: requests.Session,
    config: BackendConfig,
    method: str,
    path: str,
    *,
    params: Optional[dict[str, Any]] = None,
    json_body: Optional[dict[str, Any]] = None,
) -> Any:
    """Wysyła request do FastAPI i zwraca JSON."""
    url = f"{config.api_root}{path}"
    response = session.request(
        method=method,
        url=url,
        params=params,
        json=json_body,
        timeout=config.timeout_seconds,
    )

    if response.status_code >= 400:
        body = response.text.strip()
        raise RuntimeError(
            f"Backend returned {response.status_code} for {path}: {body or 'empty response'}"
        )

    if not response.content:
        return None
    return response.json()


def request_absolute_json(
    session: requests.Session,
    config: BackendConfig,
    method: str,
    absolute_url: str,
) -> Any:
    """Wysyła request do pełnego URL."""
    response = session.request(
        method=method,
        url=absolute_url,
        timeout=config.timeout_seconds,
    )
    if response.status_code >= 400:
        body = response.text.strip()
        raise RuntimeError(
            f"Backend returned {response.status_code} for {absolute_url}: {body or 'empty response'}"
        )
    return response.json() if response.content else None


def pretty(data: Any) -> str:
    """Format pomocniczy dla klientów lubiących tekstowy output."""
    return json.dumps(data, ensure_ascii=False, indent=2)


def create_mcp_server(runtime_config: Optional[RuntimeConfig] = None):
    """Buduje instancję MCP servera."""
    if FastMCP is None:
        raise RuntimeError(
            "Brakuje pakietu 'mcp'. Zainstaluj zależności: pip install -r requirements.txt"
        )

    runtime = runtime_config or load_runtime_config()
    config = load_backend_config()
    session = build_session(config)
    mcp = FastMCP(
        "garmin-ai",
        host=runtime.host,
        port=runtime.port,
        streamable_http_path=runtime.streamable_http_path,
    )

    @mcp.tool()
    def healthcheck() -> dict[str, Any]:
        """Sprawdza czy backend Garmin AI odpowiada."""
        return request_absolute_json(
            session,
            config,
            "GET",
            f"{config.backend_url.rstrip('/')}/health",
        )

    @mcp.tool()
    def get_training_plan() -> dict[str, Any]:
        """Pobiera plan treningowy, profil użytkownika i ostatnie notatki agenta."""
        return request_json(session, config, "GET", "/athlete/training-plan")

    @mcp.tool()
    def get_athlete_snapshot(
        target_date: Optional[str] = None,
        sync_live: bool = False,
        recent_days: int = 14,
        activity_limit: int = 12,
    ) -> dict[str, Any]:
        """Zwraca pełny snapshot zawodnika do analizy i planowania treningu."""
        payload = {
            "target_date": target_date,
            "sync_live": sync_live,
            "recent_days": recent_days,
            "activity_limit": activity_limit,
        }
        return request_json(session, config, "POST", "/athlete/snapshot", json_body=payload)

    @mcp.tool()
    def refresh_and_get_snapshot(
        target_date: Optional[str] = None,
        recent_days: int = 14,
        activity_limit: int = 12,
    ) -> dict[str, Any]:
        """Wymusza świeży sync z Garmin i zwraca nowy snapshot zawodnika."""
        payload = {
            "target_date": target_date,
            "sync_live": True,
            "recent_days": recent_days,
            "activity_limit": activity_limit,
        }
        return request_json(session, config, "POST", "/athlete/snapshot", json_body=payload)

    @mcp.tool()
    def get_recent_activities(
        days: int = 30,
        activity_type: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        include_details: bool = True,
    ) -> dict[str, Any]:
        """Pobiera historię treningów z zapisanymi parametrami."""
        params = {
            "days": days,
            "activity_type": activity_type,
            "limit": limit,
            "offset": offset,
            "include_raw": False,
            "include_details": include_details,
        }
        return request_json(session, config, "GET", "/activities/history", params=params)

    @mcp.tool()
    def get_activity_details(
        activity_id: int,
        include_details: bool = True,
    ) -> dict[str, Any]:
        """Pobiera pełny zapis jednej aktywności."""
        params = {
            "include_raw": False,
            "include_details": include_details,
        }
        return request_json(
            session,
            config,
            "GET",
            f"/activities/{activity_id}",
            params=params,
        )

    @mcp.tool()
    def get_readiness(target_date: Optional[str] = None) -> dict[str, Any]:
        """Pobiera readiness score dla konkretnego dnia."""
        return request_json(
            session,
            config,
            "GET",
            "/readiness",
            params={"target_date": target_date},
        )

    @mcp.tool()
    def get_sleep_trends(days: int = 7) -> dict[str, Any]:
        """Pobiera trendy i regularność snu."""
        return request_json(session, config, "GET", "/sleep/trends", params={"days": days})

    @mcp.tool()
    def get_hrv_analysis(days: int = 7) -> dict[str, Any]:
        """Pobiera analizę HRV i ryzyka przetrenowania."""
        return request_json(session, config, "GET", "/hrv/analysis", params={"days": days})

    @mcp.tool()
    def generate_training_suggestion(
        target_date: Optional[str] = None,
        quick_note: Optional[str] = None,
        send_email: bool = False,
    ) -> dict[str, Any]:
        """Generuje nową sugestię treningową na podstawie aktualnych danych."""
        payload = {
            "target_date": target_date,
            "quick_note": quick_note,
            "send_email": send_email,
        }
        return request_json(
            session,
            config,
            "POST",
            "/actions/training-suggestion",
            json_body=payload,
        )

    @mcp.tool()
    def generate_daily_report(
        target_date: Optional[str] = None,
        quick_note: Optional[str] = None,
        send_notifications: bool = False,
    ) -> dict[str, Any]:
        """Generuje pełny raport dzienny po synchronizacji z Garmin."""
        payload = {
            "target_date": target_date,
            "quick_note": quick_note,
            "send_notifications": send_notifications,
        }
        return request_json(
            session,
            config,
            "POST",
            "/actions/report",
            json_body=payload,
        )

    return mcp


def main() -> None:
    """Uruchamia MCP server."""
    runtime = load_runtime_config()
    server = create_mcp_server(runtime)
    server.run(transport=runtime.transport, mount_path=runtime.mount_path)


if __name__ == "__main__":
    main()
