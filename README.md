# Garmin AI Analytics

Automatyczny agent AI do analizy danych z Garmin Connect - HRV, sen, regeneracja i rekomendacje treningowe z codziennym raportem na WhatsApp.

## 🎯 Funkcjonalności

### Automatyczny Import Danych
- Codzienna synchronizacja danych z Garmin Connect
- HRV (zmienność rytmu serca)
- Spoczynkowe tętno (RHR)
- Dane o śnie (długość, fazy, jakość)
- Aktywności treningowe
- Body Battery i poziomy stresu
- Masa ciała i VO2max (jeśli dostępne)

### Zaawansowana Analiza
- **Gotowość do treningu** - kompleksowy wskaźnik (0-100) na podstawie HRV, snu, RHR i obciążenia
- **Trendy HRV** - wykrywanie przetrenowania i ocena regeneracji
- **Analiza snu** - jakość, regularność i wpływ na wydolność
- **Śledzenie aktywności** - obciążenie treningowe i rekomendacje
- **Masa ciała i VO2max** - śledzenie składu ciała i wydolności

### AI Personal Trainer
- Dzienne podsumowania z interpretacją metryk
- Personalizowane rekomendacje dopasowane do Twojego profilu
- **Notatnik trenera** - agent sam zapisuje obserwacje i trendy między sesjami
- Codzienny raport wysyłany na WhatsApp (Twilio)

## 📁 Struktura Projektu

```
garmin-ai/
├── app/
│   ├── collectors/         # Pobieranie danych z Garmin
│   │   ├── garmin_client.py
│   │   ├── sync_daily.py
│   │   └── sync_activities.py
│   ├── processors/         # Analiza metryk
│   │   ├── sleep_metrics.py
│   │   ├── hrv_metrics.py
│   │   └── recovery_score.py
│   ├── db/                 # Baza danych
│   │   ├── models.py
│   │   └── repository.py
│   ├── ai/                 # Moduł AI
│   │   ├── prompts.py
│   │   └── insights.py
│   └── notifications/      # Powiadomienia
│       └── whatsapp.py
├── scripts/                # Skrypty do uruchamiania
│   ├── run_daily_sync.py
│   ├── generate_daily_report.py
│   └── setup_garmin_2fa.py
├── user_context.md         # Twój profil treningowy (edytuj!)
├── agent_notes.md          # Notatnik trenera AI (auto-generowany)
├── .env                    # Konfiguracja (nie commituj!)
└── requirements.txt        # Zależności Python
```

## 🚀 Instalacja

### 1. Setup środowiska

```bash
cd garmin-ai
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Konfiguracja `.env`

Skopiuj przykładowy plik i uzupełnij dane:
```bash
cp .env.example .env
```

Minimalna konfiguracja:
```env
GARMIN_EMAIL=twoj_email@garmin.com
GARMIN_PASSWORD=twoje_haslo
OPENAI_API_KEY=sk-your-api-key
```

### 3. Konfiguracja 2FA Garmin (jednorazowo)

Jeśli masz włączone 2FA na koncie Garmin:
```bash
./bin/python scripts/setup_garmin_2fa.py
```

Skrypt:
1. Zaloguje się do Garmin i wyśle kod na maila
2. Wprowadź kod lub kliknij link w mailu
3. Tokeny OAuth zostaną zapisane w `.garmin_tokens/`
4. **Następne logowania będą automatyczne — operacja jednorazowa**

> Tokeny są ważne miesiącami, nie musisz tego powtarzać.

### 4. Pierwsze uruchomienie

```bash
# Synchronizacja danych (ostatnie 7 dni)
./bin/python scripts/run_daily_sync.py

# Generowanie raportu
./bin/python scripts/generate_daily_report.py
```

## 👤 Personalizacja profilu (`user_context.md`)

Plik `user_context.md` to Twój profil treningowy — agent AI czyta go przy każdej sesji i dopasowuje rekomendacje do Twoich celów i ograniczeń.

**Edytuj go ręcznie**, wpisując:
- Główny cel treningowy (np. HYROX, triathlon, redukcja wagi)
- Plan tygodniowy (ile dni, jakie treningi)
- Ograniczenia i kontuzje
- Nadchodzące wyścigi/starty
- Dodatkowe informacje (sen, dieta, stres)

Przykład:
```markdown
## Cel główny
Przygotowanie do HYROX w maju 2026, aktualnie faza budowania bazy.

## Plan tygodniowy
- Pon/Śr/Pt: siła (push/pull/legs)
- Wt/Czw: bieganie (łącznie ~30 km)
- Sob: długi bieg lub HYROX simulation
- Nd: regeneracja

## Ograniczenia
Delikatne kolano prawe — unikać głębokich przysiadów i zbiegania.
```

## 🧠 Notatnik trenera (`agent_notes.md`)

Plik `agent_notes.md` to pamięć długoterminowa agenta. Po każdym raporcie AI **automatycznie dopisuje** datowane obserwacje — trendy które widzi, niepokojące wzorce, postępy.

Przykładowy wpis generowany przez agenta:
```
## 2026-03-12
- Masa ciała rośnie 2. tydzień z rzędu (87.2 kg) — monitorować
- Sen poniżej 6h przez 3 noce z rzędu — sprawdzić przy kolejnej sesji
- HYROX 73 min przy gotowości 61.8 — dobra determinacja, ryzyko kumulacji zmęczenia
```

**Możesz też sam dodawać notatki** — np. o kontuzjach, zmianach planu, ważnych wydarzeniach. Agent uwzględni je przy analizie.

> Plik rośnie z każdym dniem — agent widzi ostatnie 30 wpisów, więc historia nigdy nie "przepełni" kontekstu.

## 📱 Raporty WhatsApp (Twilio)

Codzienny raport jest automatycznie wysyłany na WhatsApp po wygenerowaniu.

### Krok 1: Konto Twilio

1. Zarejestruj się na [twilio.com](https://www.twilio.com) (konto trial z ~15$ kredytem)
2. W konsoli skopiuj **Account SID** i **Auth Token**

### Krok 2: WhatsApp Sandbox (testowy, bez opłat)

1. W konsoli Twilio → *Messaging → Try it out → Send a WhatsApp message*
2. Wyślij SMS z Twojego telefonu: `join <słowo-sandbox>` na numer `+1 415 523 8886`
3. Poczekaj na potwierdzenie — Sandbox aktywny

### Krok 3: Uzupełnij `.env`

```env
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
TWILIO_WHATSAPP_TO=whatsapp:+48TWÓJNUMER
```

### Krok 4: Test

```bash
./bin/python scripts/generate_daily_report.py
```

Na końcu raportu pojawi się `📱 Raport wysłany na WhatsApp ✓`

### Format wiadomości

```
🏃 *Raport Garmin AI — 2026-03-12*

🟡 *Gotowość:* 73/100 (MODERATE)
😴 *Sen:* 6.6 h  |  jakość 80/100
💓 *HRV:* 80  |  trend STABLE  (+1.2%)
⚖️  *Waga:* 87.2 kg
🫁 *VO2max:* 47.4 ml/kg/min

📋 *Rekomendacja:* Umiarkowana gotowość...

🤖 *AI:*
Dziś gotowość na poziomie 73/100...
```

> Jeśli zmienne Twilio nie są ustawione w `.env`, wysyłka jest po prostu pomijana — raport generuje się normalnie.

## ⚙️ Automatyzacja (cron)

Ustaw cron żeby raporty przychodziły automatycznie co rano:

```bash
crontab -e
```

Dodaj:
```
# Synchronizacja danych o 6:00
0 6 * * * cd /Users/grucha/Documents/Garmin/Proj_API/garmin-ai && ./bin/python scripts/run_daily_sync.py >> logs/cron_sync.log 2>&1

# Raport i WhatsApp o 7:00
0 7 * * * cd /Users/grucha/Documents/Garmin/Proj_API/garmin-ai && ./bin/python scripts/generate_daily_report.py >> logs/cron_report.log 2>&1
```

## 📈 Jak działa analiza

### Gotowość do Treningu (0-100)
- **HRV (40%)** — względem baseline 28-dniowego
- **Sen (35%)** — jakość i długość
- **RHR (15%)** — odchylenie od baseline
- **Obciążenie (10%)** — ostatnie 7 dni

| Wynik | Kategoria | Rekomendacja |
|-------|-----------|--------------|
| 80–100 | Doskonała | Intensywny trening OK |
| 65–79 | Dobra | Normalny trening |
| 50–64 | Umiarkowana | Lekki trening |
| 35–49 | Niska | Odpoczynek aktywny |
| 0–34 | Bardzo niska | Pełen odpoczynek |

### Wykrywanie Przetrenowania
Analiza ostatnich 14 dni HRV:
- ≥3 dni bardzo niskiego HRV → **wysokie ryzyko**
- ≥2 dni bardzo niskiego lub ≥5 niskiego → **umiarkowane**
- 3–4 dni niskiego HRV → **niskie**
- Inne → **minimalne**

## 📝 Baza Danych

SQLite (domyślnie) — plik `garmin_data.db`, brak dodatkowej konfiguracji.

Tabele:
- `daily_metrics` — statystyki dzienne
- `sleep_sessions` — dane o śnie
- `hrv_data` — zmienność rytmu serca
- `resting_heart_rate` — spoczynkowe tętno
- `activities` — aktywności treningowe
- `recovery_metrics` — obliczone wskaźniki gotowości
- `body_weight` — masa ciała i skład ciała
- `vo2max_data` — dane VO2max
- `ai_insights` — insighty i podsumowania z AI

Opcjonalnie PostgreSQL:
```env
DATABASE_URL=postgresql://user:password@localhost:5432/garmin_ai
```

## 🔒 Bezpieczeństwo

- **Nigdy nie commituj** pliku `.env` ani katalogu `.garmin_tokens/` (są w `.gitignore`)
- `agent_notes.md` i `user_context.md` zawierają dane osobowe — nie commituj jeśli repozytorium jest publiczne

## 🐛 Troubleshooting

### Błąd autoryzacji Garmin / 2FA
```bash
./bin/python scripts/setup_garmin_2fa.py
```

### Sen/HRV pokazuje 0 lub brak danych
- Sprawdź czy dane są widoczne w Garmin Connect web
- HRV wymaga kompatybilnego zegarka z pulsometrem

### AI nie działa
- Sprawdź czy `OPENAI_API_KEY` jest ustawiony w `.env`
- Sprawdź limity i billing w OpenAI (platform.openai.com)

### WhatsApp nie wysyła
- Sprawdź czy numer Sandbox jest aktywny (ważny 72h od dołączenia — wyślij ponownie `join <słowo>` jeśli wygasł)
- Sprawdź logi: `logs/daily_report.log`

### Logi
```
logs/sync_daily.log       # Synchronizacja danych
logs/daily_report.log     # Generowanie raportu
```

## 🙏 Podziękowania

- [garminconnect](https://github.com/cyberjunky/python-garminconnect) — Python API dla Garmin Connect
- [OpenAI](https://openai.com/) — API dla funkcji AI
- [Twilio](https://www.twilio.com/) — WhatsApp API

