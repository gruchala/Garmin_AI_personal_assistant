"""Główna aplikacja FastAPI"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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
    allow_origins=["*"],  # W produkcji ogranicz do konkretnych domen
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dodanie routerów
app.include_router(router, prefix="/api/v1")


@app.get("/")
async def root():
    """Endpoint główny"""
    return RedirectResponse(url="/api/v1/dashboard")


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
