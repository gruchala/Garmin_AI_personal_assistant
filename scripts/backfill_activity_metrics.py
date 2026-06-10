"""Uzupełnia szerokie kolumny aktywności z istniejących payloadów raw_data."""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.models import Activity, ActivityDetail, init_db
from app.db.repository import GarminRepository


logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def main() -> None:
    engine, session_factory = init_db()
    session = session_factory()
    repository = GarminRepository(session)

    try:
        activities = session.query(Activity).all()
        details = session.query(ActivityDetail).all()

        for activity in activities:
            if isinstance(activity.raw_data, dict):
                repository.save_activity(activity.raw_data)

        for detail in details:
            if isinstance(detail.raw_data, dict):
                repository.save_activity_details(detail.activity_id, detail.raw_data)

        print(
            f"Uzupełniono {len(activities)} aktywności "
            f"i {len(details)} rekordów szczegółowych."
        )
    finally:
        session.close()
        engine.dispose()


if __name__ == "__main__":
    main()
