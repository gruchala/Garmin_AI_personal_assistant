"""Routy API"""

import logging
from html import escape
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional, List
import markdown
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db.repository import GarminRepository
from ..collectors.garmin_client import GarminClient
from ..collectors.sync_daily import DailyDataSync
from ..collectors.sync_activities import ActivitiesSync
from ..processors.recovery_score import RecoveryScore
from ..processors.sleep_metrics import SleepMetrics
from ..processors.hrv_metrics import HRVMetrics
from ..ai.insights import InsightsGenerator, InsightsAssistant
from ..services.workflows import build_daily_report, build_training_suggestion

logger = logging.getLogger(__name__)

router = APIRouter()
dashboard_path = Path(__file__).with_name("dashboard.html")
project_root = Path(__file__).resolve().parents[2]
editable_files = {
    "user_context.md": {
        "path": project_root / "user_context.md",
        "label": "Profil użytkownika",
        "kind": "markdown",
        "description": "Plik z profilem i ograniczeniami treningowymi użytkownika.",
    },
    "training_plan.md": {
        "path": project_root / "training_plan.md",
        "label": "Plan treningowy",
        "kind": "markdown",
        "description": "Tygodniowy plan i notatki do sugestii treningowych.",
    },
    "agent_notes.md": {
        "path": project_root / "agent_notes.md",
        "label": "Notes agenta",
        "kind": "markdown",
        "description": "Długoterminowe notatki, które agent sam dopisuje po analizie.",
    },
}


# === MODELE PYDANTIC ===

class SyncRequest(BaseModel):
    """Request do synchronizacji danych"""
    email: str
    password: str
    days: Optional[int] = 7


class ChatRequest(BaseModel):
    """Request do czatu z AI"""
    message: str
    include_context: bool = True


class TrainingQuestion(BaseModel):
    """Pytanie o trening"""
    question: str


class ReportActionRequest(BaseModel):
    """Request do świeżego raportu"""
    target_date: Optional[str] = None
    send_notifications: bool = False
    quick_note: Optional[str] = None


class TrainingSuggestionRequest(BaseModel):
    """Request do świeżej propozycji treningowej"""
    target_date: Optional[str] = None
    send_email: bool = False
    quick_note: Optional[str] = None


class FileUpdateRequest(BaseModel):
    """Request do zapisu pliku tekstowego/markdown."""
    content: str


class FilePreviewRequest(BaseModel):
    """Request do renderowania podglądu Markdown bez zapisu."""
    content: str
    kind: str = "markdown"


def get_editable_file_or_404(file_name: str) -> dict:
    """Zwraca konfigurację dozwolonego pliku albo 404."""
    file_info = editable_files.get(file_name)
    if not file_info:
        raise HTTPException(status_code=404, detail="Taki plik nie jest dostępny w edytorze")
    return file_info


def render_markdown_preview(content: str) -> str:
    """Renderuje Markdown do bezpiecznego podglądu HTML w panelu."""
    safe_content = escape(content)
    return markdown.markdown(
        safe_content,
        extensions=[
            "extra",
            "fenced_code",
            "tables",
            "sane_lists",
            "nl2br",
            "codehilite",
        ],
        extension_configs={
            "codehilite": {
                "guess_lang": False,
                "linenums": False,
                "css_class": "codehilite",
            }
        },
        output_format="html5",
    )


# === DEPENDENCY INJECTION ===

def get_db_session():
    """Dependency do pobierania sesji bazy danych"""
    from fastapi import Request
    
    def _get_session(request: Request):
        session_factory = request.app.state.session_factory
        session = session_factory()
        try:
            yield session
        finally:
            session.close()
    
    return _get_session


def parse_target_date(raw_date: Optional[str]) -> date:
    """Parsuje opcjonalną datę z requestu."""
    if not raw_date:
        return date.today()
    return datetime.strptime(raw_date, "%Y-%m-%d").date()


@router.get("/dashboard", include_in_schema=False)
async def dashboard():
    """Prosty panel webowy do ręcznych akcji."""
    return FileResponse(dashboard_path)


@router.get("/files")
async def list_editable_files():
    """Zwraca listę plików dostępnych w prostym edytorze."""
    files = []
    for name, info in editable_files.items():
        path = info["path"]
        files.append({
            "name": name,
            "label": info["label"],
            "kind": info["kind"],
            "description": info["description"],
            "exists": path.exists(),
            "size": path.stat().st_size if path.exists() else 0,
        })
    return {"files": files}


@router.get("/files/{file_name}")
async def get_editable_file(file_name: str):
    """Odczytuje plik dostępny w edytorze."""
    file_info = get_editable_file_or_404(file_name)
    path = file_info["path"]

    content = path.read_text(encoding="utf-8") if path.exists() else ""
    return {
        "name": file_name,
        "label": file_info["label"],
        "kind": file_info["kind"],
        "description": file_info["description"],
        "exists": path.exists(),
        "content": content,
        "preview_html": render_markdown_preview(content),
        "updated_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat() if path.exists() else None,
    }


@router.post("/files/preview")
async def preview_editable_file(payload: FilePreviewRequest):
    """Renderuje roboczy podgląd pliku bez zapisywania na dysk."""
    if payload.kind == "markdown":
        preview_html = render_markdown_preview(payload.content)
    else:
        preview_html = f"<pre>{escape(payload.content)}</pre>"

    return {
        "kind": payload.kind,
        "preview_html": preview_html,
    }


@router.put("/files/{file_name}")
async def save_editable_file(file_name: str, payload: FileUpdateRequest):
    """Zapisuje plik dostępny w edytorze."""
    file_info = get_editable_file_or_404(file_name)
    path = file_info["path"]
    path.write_text(payload.content, encoding="utf-8")

    return {
        "status": "success",
        "name": file_name,
        "message": f"Zapisano {file_name}",
        "preview_html": render_markdown_preview(payload.content),
        "updated_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
        "size": path.stat().st_size,
    }


# === ENDPOINTY SYNCHRONIZACJI ===

@router.post("/sync/daily")
async def sync_daily_data(
    sync_request: SyncRequest,
    session: Session = Depends(get_db_session())
):
    """
    Synchronizuje dane dzienne z Garmin Connect
    """
    try:
        # Połączenie z Garmin
        client = GarminClient(sync_request.email, sync_request.password)
        if not client.connect():
            raise HTTPException(status_code=401, detail="Nie udało się połączyć z Garmin Connect")
        
        # Synchronizacja
        repo = GarminRepository(session)
        sync = DailyDataSync(client, repo)
        
        synced_count = sync.sync_last_n_days(sync_request.days)
        
        return {
            "status": "success",
            "synced_days": synced_count,
            "message": f"Zsynchronizowano {synced_count} dni"
        }
        
    except Exception as e:
        logger.error(f"Błąd podczas synchronizacji: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync/activities")
async def sync_activities(
    sync_request: SyncRequest,
    session: Session = Depends(get_db_session())
):
    """
    Synchronizuje aktywności z Garmin Connect
    """
    try:
        # Połączenie z Garmin
        client = GarminClient(sync_request.email, sync_request.password)
        if not client.connect():
            raise HTTPException(status_code=401, detail="Nie udało się połączyć z Garmin Connect")
        
        # Synchronizacja
        repo = GarminRepository(session)
        sync = ActivitiesSync(client, repo)
        
        synced_count = sync.sync_recent_activities(20)
        
        return {
            "status": "success",
            "synced_activities": synced_count,
            "message": f"Zsynchronizowano {synced_count} aktywności"
        }
        
    except Exception as e:
        logger.error(f"Błąd podczas synchronizacji aktywności: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/actions/report")
async def generate_fresh_report(
    action_request: ReportActionRequest,
    session: Session = Depends(get_db_session())
):
    """Robi pełny sync i generuje świeży raport."""
    try:
        target_date = parse_target_date(action_request.target_date)
        repo = GarminRepository(session)
        return build_daily_report(
            repository=repo,
            target_date=target_date,
            send_notifications=action_request.send_notifications,
            quick_note=action_request.quick_note,
        )
    except Exception as e:
        logger.error(f"Błąd podczas generowania świeżego raportu: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/actions/training-suggestion")
async def generate_fresh_training_suggestion(
    action_request: TrainingSuggestionRequest,
    session: Session = Depends(get_db_session())
):
    """Robi pełny sync i generuje świeżą propozycję treningową."""
    try:
        target_date = parse_target_date(action_request.target_date)
        repo = GarminRepository(session)
        return build_training_suggestion(
            repository=repo,
            target_date=target_date,
            send_email=action_request.send_email,
            quick_note=action_request.quick_note,
        )
    except Exception as e:
        logger.error(f"Błąd podczas generowania propozycji treningowej: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# === ENDPOINTY DANYCH ===

@router.get("/readiness")
async def get_readiness(
    target_date: Optional[str] = None,
    session: Session = Depends(get_db_session())
):
    """
    Pobiera gotowość do treningu dla konkretnego dnia
    """
    try:
        if target_date:
            date_obj = datetime.strptime(target_date, "%Y-%m-%d").date()
        else:
            date_obj = date.today()
        
        repo = GarminRepository(session)
        recovery = RecoveryScore(repo)
        
        readiness = recovery.calculate_daily_readiness(date_obj)
        
        return readiness
        
    except Exception as e:
        logger.error(f"Błąd podczas obliczania gotowości: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/readiness/weekly")
async def get_weekly_readiness(
    session: Session = Depends(get_db_session())
):
    """
    Pobiera tygodniowy raport gotowości
    """
    try:
        repo = GarminRepository(session)
        recovery = RecoveryScore(repo)
        
        report = recovery.get_weekly_recovery_report()
        
        return report
        
    except Exception as e:
        logger.error(f"Błąd podczas generowania raportu tygodniowego: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sleep/trends")
async def get_sleep_trends(
    days: int = Query(7, ge=1, le=90),
    session: Session = Depends(get_db_session())
):
    """
    Pobiera trendy snu
    """
    try:
        repo = GarminRepository(session)
        sleep_metrics = SleepMetrics(repo)
        
        trends = sleep_metrics.get_sleep_trends(days)
        consistency = sleep_metrics.analyze_sleep_consistency(days)
        
        return {
            "trends": trends,
            "consistency": consistency
        }
        
    except Exception as e:
        logger.error(f"Błąd podczas analizy snu: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/hrv/analysis")
async def get_hrv_analysis(
    days: int = Query(7, ge=1, le=90),
    session: Session = Depends(get_db_session())
):
    """
    Pobiera analizę HRV
    """
    try:
        repo = GarminRepository(session)
        hrv_metrics = HRVMetrics(repo)
        
        baseline = hrv_metrics.calculate_baseline(28)
        trend = hrv_metrics.get_hrv_trend(days)
        overtraining = hrv_metrics.detect_overtraining_risk(14)
        
        return {
            "baseline": baseline,
            "trend": trend,
            "overtraining_risk": overtraining
        }
        
    except Exception as e:
        logger.error(f"Błąd podczas analizy HRV: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/activities/summary")
async def get_activities_summary(
    days: int = Query(7, ge=1, le=90),
    session: Session = Depends(get_db_session())
):
    """
    Pobiera podsumowanie aktywności
    """
    try:
        end_date = date.today()
        start_date = end_date - timedelta(days=days - 1)
        
        repo = GarminRepository(session)
        activities = repo.get_activities_in_date_range(start_date, end_date)
        
        # Oblicz podsumowanie
        total_distance = sum(a.get('distance', 0) for a in activities) / 1000
        total_duration = sum(a.get('duration', 0) for a in activities) / 3600
        total_calories = sum(a.get('calories', 0) for a in activities)
        
        activity_types = {}
        for activity in activities:
            atype = activity.get('activityType', 'unknown')
            if atype not in activity_types:
                activity_types[atype] = {'count': 0, 'distance': 0, 'duration': 0}
            
            activity_types[atype]['count'] += 1
            activity_types[atype]['distance'] += activity.get('distance', 0) / 1000
            activity_types[atype]['duration'] += activity.get('duration', 0) / 3600
        
        return {
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "days": days
            },
            "summary": {
                "total_activities": len(activities),
                "total_distance_km": round(total_distance, 2),
                "total_duration_hours": round(total_duration, 2),
                "total_calories": total_calories
            },
            "by_type": activity_types
        }
        
    except Exception as e:
        logger.error(f"Błąd podczas generowania podsumowania aktywności: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/activities/history")
async def get_activities_history(
    days: int = Query(90, ge=1, le=3650),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    activity_type: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    include_raw: bool = True,
    include_details: bool = True,
    session: Session = Depends(get_db_session()),
):
    """Zwraca historię treningów ze wszystkimi zapisanymi parametrami."""
    try:
        parsed_end = datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else date.today()
        parsed_start = (
            datetime.strptime(start_date, "%Y-%m-%d").date()
            if start_date
            else parsed_end - timedelta(days=days - 1)
        )
        if parsed_start > parsed_end:
            raise HTTPException(status_code=422, detail="start_date nie może być późniejsza niż end_date")

        repo = GarminRepository(session)
        history = repo.get_activity_history(
            start_date=parsed_start,
            end_date=parsed_end,
            activity_type=activity_type,
            limit=limit,
            offset=offset,
            include_raw=include_raw,
            include_details=include_details,
        )
        return {
            "period": {
                "start": parsed_start.isoformat(),
                "end": parsed_end.isoformat(),
            },
            "activity_type": activity_type,
            **history,
        }
    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(status_code=422, detail="Daty muszą mieć format YYYY-MM-DD")
    except Exception as e:
        logger.error(f"Błąd podczas pobierania historii aktywności: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/activities/{activity_id}")
async def get_activity_details(
    activity_id: int,
    include_raw: bool = True,
    include_details: bool = True,
    session: Session = Depends(get_db_session()),
):
    """Zwraca pełny zapis jednego treningu."""
    try:
        repo = GarminRepository(session)
        activity = repo.get_activity_document(
            activity_id=activity_id,
            include_raw=include_raw,
            include_details=include_details,
        )
        if not activity:
            raise HTTPException(status_code=404, detail="Nie znaleziono aktywności")
        return activity
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Błąd podczas pobierania aktywności {activity_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# === ENDPOINTY AI ===

@router.get("/insights/daily")
async def get_daily_insight(
    target_date: Optional[str] = None,
    session: Session = Depends(get_db_session())
):
    """
    Generuje insight dla konkretnego dnia
    """
    try:
        if target_date:
            date_obj = datetime.strptime(target_date, "%Y-%m-%d").date()
        else:
            date_obj = date.today()
        
        repo = GarminRepository(session)
        ai = InsightsGenerator()
        assistant = InsightsAssistant(repo, ai)
        
        insight = assistant.get_daily_insight(date_obj)
        
        if not insight:
            raise HTTPException(
                status_code=503,
                detail="Brak klucza API OpenAI - generowanie insightów niedostępne"
            )
        
        return {
            "date": date_obj.isoformat(),
            "insight": insight
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Błąd podczas generowania insightu: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/insights/training-question")
async def ask_training_question(
    question: TrainingQuestion,
    session: Session = Depends(get_db_session())
):
    """
    Zadaje pytanie o trening
    """
    try:
        repo = GarminRepository(session)
        recovery = RecoveryScore(repo)
        ai = InsightsGenerator()
        
        # Pobierz kontekst
        readiness = recovery.calculate_daily_readiness()
        
        end_date = date.today()
        start_date = end_date - timedelta(days=6)
        activities = repo.get_activities_in_date_range(start_date, end_date)
        
        # Oblicz obciążenie
        training_load = {
            'total_load': sum(a.get('duration', 0) / 3600 for a in activities),
            'activity_count': len(activities)
        }
        
        answer = ai.answer_training_question(
            question=question.question,
            readiness=readiness,
            recent_activities=activities,
            training_load=training_load
        )
        
        if not answer:
            raise HTTPException(
                status_code=503,
                detail="Brak klucza API OpenAI"
            )
        
        return {
            "question": question.question,
            "answer": answer,
            "context": {
                "readiness_score": readiness.get('readiness_score'),
                "recent_activities_count": len(activities)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Błąd podczas odpowiadania na pytanie: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat")
async def chat_with_ai(
    chat_request: ChatRequest,
    session: Session = Depends(get_db_session())
):
    """
    Czat z AI z kontekstem danych
    """
    try:
        ai = InsightsGenerator()
        
        context = None
        if chat_request.include_context:
            repo = GarminRepository(session)
            recovery = RecoveryScore(repo)
            
            # Zbierz podstawowy kontekst
            readiness = recovery.calculate_daily_readiness()
            
            context = {
                'readiness_score': readiness.get('readiness_score'),
                'category': readiness.get('category'),
                'recommendation': readiness.get('recommendation')
            }
        
        answer = ai.chat(chat_request.message, context)
        
        if not answer:
            raise HTTPException(
                status_code=503,
                detail="Brak klucza API OpenAI"
            )
        
        return {
            "message": chat_request.message,
            "answer": answer
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Błąd podczas czatu: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/insights/recent")
async def get_recent_insights(
    days: int = Query(7, ge=1, le=30),
    unread_only: bool = False,
    session: Session = Depends(get_db_session())
):
    """
    Pobiera ostatnie insighty
    """
    try:
        repo = GarminRepository(session)
        insights = repo.get_recent_insights(days, unread_only)
        
        return {
            "insights": [
                {
                    "id": i.id,
                    "date": i.date.isoformat(),
                    "type": i.insight_type,
                    "title": i.title,
                    "content": i.content,
                    "priority": i.priority,
                    "is_read": i.is_read,
                    "created_at": i.created_at.isoformat()
                }
                for i in insights
            ],
            "count": len(insights)
        }
        
    except Exception as e:
        logger.error(f"Błąd podczas pobierania insightów: {e}")
        raise HTTPException(status_code=500, detail=str(e))
