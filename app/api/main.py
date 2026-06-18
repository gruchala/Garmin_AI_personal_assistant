"""Główna aplikacja FastAPI"""

import logging
import os
from secrets import compare_digest
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv
from .routes import router
from ..db.models import init_db

load_dotenv()

# Konfiguracja logowania
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def _parse_origins_from_env(raw_value: str | None) -> list[str]:
    """Parsuje listę originów CORS z CSV w env."""
    if not raw_value:
        return ["*"]
    origins = [item.strip() for item in raw_value.split(",") if item.strip()]
    return origins or ["*"]


API_AUTH_TOKEN = (os.getenv("AGENT_API_TOKEN") or "").strip()
API_AUTH_HEADER = (os.getenv("AGENT_API_HEADER") or "X-Agent-Token").strip()
PUBLIC_HEALTHCHECK = (os.getenv("PUBLIC_HEALTHCHECK") or "true").strip().lower() == "true"
CORS_ALLOW_ORIGINS = _parse_origins_from_env(os.getenv("CORS_ALLOW_ORIGINS"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle management dla aplikacji"""
    # Startup
    logger.info("Uruchamianie aplikacji Garmin AI...")
    
    # Inicjalizacja bazy danych
    engine, session_factory = init_db()
    app.state.db_engine = engine
    app.state.session_factory = session_factory
    logger.info("Baza danych zainicjalizowana")
    
    yield
    
    # Shutdown
    logger.info("Zamykanie aplikacji...")
    app.state.db_engine.dispose()


# Tworzenie aplikacji FastAPI
app = FastAPI(
    title="Garmin AI Analytics",
    description="API do automatycznej analizy danych z Garmin Connect",
    version="0.1.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    # Dla publicznego API z tokenem nagłówkowym (bez cookies) ustawiamy false,
    # żeby można było używać Access-Control-Allow-Origin: *.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def api_token_auth_middleware(request: Request, call_next):
    """Chroni endpointy API tokenem w nagłówku lub Bearer tokenem."""
    # Przeglądarki muszą przejść preflight CORS zanim wyślą właściwe żądanie.
    if request.method == "OPTIONS":
        return await call_next(request)

    if not API_AUTH_TOKEN:
        return await call_next(request)

    path = request.url.path
    is_health = path == "/health"
    is_docs = path in {"/docs", "/openapi.json", "/redoc"}
    is_dashboard = path in {"/", "/api/v1/dashboard"}
    protected_api = path.startswith("/api/")

    if is_docs or is_dashboard:
        return await call_next(request)
    if is_health and PUBLIC_HEALTHCHECK:
        return await call_next(request)
    if not protected_api and not is_health:
        return await call_next(request)

    token_from_header = (request.headers.get(API_AUTH_HEADER) or "").strip()
    auth_header = (request.headers.get("Authorization") or "").strip()
    bearer_token = auth_header[7:].strip() if auth_header.lower().startswith("bearer ") else ""

    valid_header = bool(token_from_header) and compare_digest(token_from_header, API_AUTH_TOKEN)
    valid_bearer = bool(bearer_token) and compare_digest(bearer_token, API_AUTH_TOKEN)

    if not (valid_header or valid_bearer):
        return JSONResponse(
            status_code=401,
            content={
                "detail": "Unauthorized - missing or invalid API token"
            },
            headers={
                "Access-Control-Allow-Origin": "*",
            },
        )

    return await call_next(request)

# Dodanie routerów
app.include_router(router, prefix="/api/v1")


@app.get("/", include_in_schema=False)
async def root():
    """Redirect obsługiwany przez Nginx — backend zwraca 404 dla bezpośrednich wywołań"""
    from fastapi import Response
    return Response(status_code=404)


@app.get("/health")
async def health_check():
    """Sprawdzenie stanu aplikacji"""
    return {
        "status": "healthy",
        "database": "connected"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
