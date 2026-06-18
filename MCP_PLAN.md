# MCP Plan Dla Garmin AI

## Co mamy dzisiaj

To nie jest gotowiec typu Grafana, Home Assistant albo GarminDB jako osobny produkt.
To jest własny stack w Pythonie:

- `FastAPI` jako warstwa HTTP/API
- `SQLAlchemy` jako ORM
- `SQLite` domyślnie, z możliwością przejścia na `PostgreSQL` przez `DATABASE_URL`
- importer Garmin oparty o `python-garminconnect` + `garth`
- własna logika analityczna dla `HRV`, snu, gotowości i obciążeń
- warstwa AI do raportów i sugestii treningowych oparta o `OpenAI`

## Jak dziś wpadają dane Garmin

Garmin wpada przez:

- bibliotekę `python-garminconnect`
- logowanie/tokeny przez `garth`
- lokalny katalog `.garmin_tokens/` dla OAuth / 2FA

Projekt już pobiera i zapisuje:

- statystyki dzienne
- sen
- HRV
- spoczynkowe tętno
- Body Battery
- stres
- aktywności
- masę ciała i skład ciała
- VO2max

## Co mamy już w bazie

Główne tabele:

- `daily_metrics`
- `sleep_sessions`
- `hrv_data`
- `resting_heart_rate`
- `activities`
- `activity_details`
- `recovery_metrics`
- `body_weight`
- `vo2max_data`
- `ai_insights`

## Co już potrafi system

- zrobić pełny sync z Garmin przed analizą
- policzyć readiness score
- policzyć trendy HRV i snu
- zapisać pełne treningi z metrykami
- uwzględnić `user_context.md`, `training_plan.md` i `agent_notes.md`
- wygenerować AI raport dzienny
- wygenerować AI sugestię treningową

## Co dołożyliśmy pod MCP

Nowe endpointy:

- `GET /api/v1/athlete/training-plan`
- `POST /api/v1/athlete/snapshot`

`athlete/snapshot` zwraca w jednym miejscu:

- readiness
- weekly recovery
- sleep today + trendy
- HRV today + baseline + trend + overtraining risk
- RHR
- Body Battery
- body composition
- VO2max
- ostatnie aktywności
- aktywności z bieżącego dnia
- plan treningowy na dany dzień
- `user_context.md`
- ostatnie `agent_notes.md`
- ostatnie insighty AI

To jest dobra warstwa bazowa pod MCP.

## Jak odpowiedzieć ChatGPT / innemu agentowi

Możesz odpowiedzieć mniej więcej tak:

> Mój system stoi na własnym stacku Pythonowym: FastAPI + SQLAlchemy. Domyślnie używam SQLite, ale projekt wspiera też PostgreSQL przez `DATABASE_URL`. Dane Garmin pobieram przez `python-garminconnect` i `garth` z tokenami OAuth/2FA zapisanymi lokalnie. Mam już import dziennych metryk, snu, HRV, RHR, Body Battery, stresu, aktywności, masy ciała i VO2max. System liczy readiness, trendy HRV/snu i generuje sugestie treningowe AI. Dodałem też endpoint snapshotu zawodnika pod MCP, żeby agent mógł pobierać pełny kontekst treningowy jednym wywołaniem.

## Najlepsza kolejność dalszych prac

1. Utrzymać FastAPI jako źródło prawdy dla danych sportowych.
2. Postawić cienki serwer MCP, który mapuje narzędzia na endpointy FastAPI.
3. Dodać autoryzację do endpointów MCP/API.
4. Rozszerzyć model danych o obiekty Hyrox, jeśli chcesz planowanie stricte pod zawody.

## Proponowane narzędzia MCP

- `get_athlete_snapshot`
- `get_training_plan`
- `get_recent_activities`
- `get_activity_details`
- `get_readiness`
- `get_sleep_trends`
- `get_hrv_analysis`
- `refresh_and_get_snapshot`
- `generate_training_suggestion`

## Co warto dodać w następnym kroku

- osobne tabele `hyrox_sessions`, `hyrox_blocks`, `hyrox_race_results`
- tagowanie aktywności: `easy`, `tempo`, `threshold`, `hyrox`, `strength`, `simulation`
- chronic load / acute load / monotony / strain
- wykrywanie jakości sesji względem planu
- prosty scoring "czy dziś robić progi / siłę / regenerację"

## Rekomendacja architektoniczna

Nie budowałbym MCP bezpośrednio na Garmin Connect.
Najlepiej:

Garmin Connect -> importer -> lokalna baza -> FastAPI -> MCP -> agent AI

To daje:

- stabilność
- pełną kontrolę nad schematem danych
- szybsze odpowiedzi
- możliwość własnych metryk i logiki treningowej
- brak zależności od chwilowych ograniczeń po stronie Garmin
