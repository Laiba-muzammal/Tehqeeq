"""
calendar_tool.py

Deterministic calendar verification tool, separate from the web-search
pipeline (searcher.py). Calendar-dependent claims (Ramadan/Roza start date,
Eid, other Hijri-calendar events) don't need to be "searched for" -- they
can be computed directly from a reliable date-conversion API. Relying on
web search alone for these claims often fails simply because there's no
recent news coverage at the moment the claim is checked (see verifier.py
revision history for the "kal roza hoga" case that motivated this).

This module fetches the current Hijri (Islamic) calendar date from a public
date-conversion API and formats it as a piece of evidence that can be
injected into the pipeline alongside (not instead of) web search results.

Uses the Aladhan API (https://aladhan.com/islamic-calendar-api), which is
free and does not require an API key.
"""

import logging
from datetime import date
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

ALADHAN_G_TO_H_URL = "https://api.aladhan.com/v1/gToH"

# Keywords that suggest a claim is about the Islamic/Hijri calendar and
# would benefit from a deterministic date check rather than (or alongside)
# web search.
CALENDAR_KEYWORDS = [
    "roza", "ramadan", "ramzan", "eid", "hijri", "islamic calendar",
    "moon sighting", "ruet-e-hilal", "shawwal", "muharram", "hijra",
]


def is_calendar_related(text: str) -> bool:
    """Cheap keyword check to decide whether to bother calling the calendar API."""
    lowered = text.lower()
    return any(keyword in lowered for keyword in CALENDAR_KEYWORDS)


def get_hijri_date_for_today(gregorian_date: date | None = None) -> dict | None:
    """
    Fetches the Hijri calendar date corresponding to a Gregorian date
    (defaults to today) from the Aladhan API.

    Returns a dict like:
        {
            "gregorian": "19-07-2026",
            "hijri_day": "4",
            "hijri_month_name": "Muharram",
            "hijri_year": "1448",
        }
    or None if the API call fails -- callers should treat this as "no
    additional evidence available" and fall back to normal web search,
    not as an error that should halt the pipeline.
    """
    target_date = gregorian_date or date.today()
    date_str = target_date.strftime("%d-%m-%Y")

    try:
        response = requests.get(
            ALADHAN_G_TO_H_URL,
            params={"date": date_str},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()

        hijri = payload["data"]["hijri"]
        return {
            "gregorian": date_str,
            "hijri_day": hijri["day"],
            "hijri_month_name": hijri["month"]["en"],
            "hijri_year": hijri["year"],
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("Hijri date lookup failed: %s", exc)
        return None


def build_calendar_evidence(gregorian_date: date | None = None) -> dict | None:
    """
    Builds a single evidence-shaped dict (same shape as searcher.py's
    results: title/url/content/is_trusted) representing the current Hijri
    date, so it can be appended directly to the evidence list passed to
    verifier.py.

    Returns None if the lookup failed.
    """
    hijri = get_hijri_date_for_today(gregorian_date)
    if hijri is None:
        return None

    content = (
        f"According to the Islamic (Hijri) calendar, the Gregorian date "
        f"{hijri['gregorian']} corresponds to {hijri['hijri_day']} "
        f"{hijri['hijri_month_name']} {hijri['hijri_year']} AH. "
        f"This is a deterministic calendar conversion, not a claim from a "
        f"news source."
    )

    return {
        "title": "Hijri calendar conversion (Aladhan API)",
        "url": "https://aladhan.com/islamic-calendar-api",
        "content": content,
        "is_trusted": True,  # deterministic date math, not a claim needing corroboration
    }


if __name__ == "__main__":
    evidence = build_calendar_evidence()
    print(evidence)