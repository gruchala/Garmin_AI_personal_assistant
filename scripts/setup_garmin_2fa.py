#!/usr/bin/env python3
"""
Skrypt do jednorazowej konfiguracji 2FA dla Garmin Connect.
Po uruchomieniu zapisuje tokeny OAuth i już nie będzie potrzebny kod 2FA.
"""

import os
import sys
from pathlib import Path
from getpass import getpass
from dotenv import load_dotenv

# Załaduj zmienne z .env
load_dotenv()

# Dodaj ścieżkę do modułu app
sys.path.insert(0, str(Path(__file__).parent.parent))

import garth
from garth.exc import GarthHTTPError


def main():
    print("=" * 70)
    print("  GARMIN CONNECT - KONFIGURACJA 2FA")
    print("=" * 70)
    print("\nTen skrypt zapisze tokeny OAuth, dzięki czemu nie będziesz już")
    print("musiał podawać kodu 2FA przy każdym logowaniu.\n")
    
    # Pobierz dane logowania
    email = os.getenv("GARMIN_EMAIL")
    password = os.getenv("GARMIN_PASSWORD")
    
    if not email:
        email = input("Email Garmin Connect: ")
    if not password:
        password = getpass("Hasło Garmin Connect: ")
    
    tokens_dir = Path(".garmin_tokens")
    tokens_dir.mkdir(exist_ok=True)
    
    # Funkcja do promptowania o kod MFA
    def prompt_for_mfa():
        print("\n⚠️  Garmin wymaga weryfikacji 2FA")
        print("Sprawdź swoją skrzynkę mailową!")
        mfa_code = input("\nWprowadź kod 2FA z maila: ").strip()
        if not mfa_code:
            print("❌ Nie podano kodu MFA")
            sys.exit(1)
        return mfa_code
    
    try:
        print("\n📧 Logowanie do Garmin Connect...")
        print("Za chwilę otrzymasz kod 2FA na maila...\n")
        
        # Zaloguj się z customowym promptem MFA
        garth.login(email, password, prompt_mfa=prompt_for_mfa)
        print("\n✓ Logowanie zakończone pomyślnie!")
        
        # Zapisz tokeny
        garth.save(tokens_dir)
        
        print(f"\n✅ SUKCES!")
        print(f"Tokeny OAuth zapisane w: {tokens_dir.absolute()}")
        print("\nOd teraz możesz uruchamiać synchronizację bez podawania kodu 2FA!")
        print("\nWażne: NIE udostępniaj katalogu .garmin_tokens nikomu!")
        print("       Zawiera on dane autoryzacyjne do Twojego konta.\n")
        
        print("=" * 70)
        print("Możesz teraz uruchomić:")
        print("  ./bin/python scripts/run_daily_sync.py")
        print("  ./bin/python scripts/generate_daily_report.py")
        print("=" * 70 + "\n")
        
    except GarthHTTPError as e:
        print(f"\n❌ Błąd połączenia z Garmin: {e}")
        print("\nSprawdź czy:")
        print("  - Email i hasło są poprawne")
        print("  - Twoje konto Garmin jest aktywne")
        print("  - Masz dostęp do internetu\n")
        sys.exit(1)
        
    except Exception as e:
        print(f"\n❌ Nieoczekiwany błąd: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
