"""Spaced repetition scheduling (SM-2 variant)."""
from datetime import date, timedelta

RATINGS = {"again": 1, "hard": 3, "good": 4, "easy": 5}
MIN_EASE = 1.3
LEARNED_DAYS = 7


def schedule(card: dict, rating: str, today: date) -> dict:
    q = RATINGS[rating]
    ease, reps, interval, lapses = card.get("ease", 2.5), card.get("reps", 0), card.get("interval", 0), card.get("lapses", 0)
    ease = max(MIN_EASE, ease + 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    if rating == "again":
        reps, interval, lapses = 0, 1, lapses + 1
    else:
        if reps == 0:
            interval = 1 if rating != "easy" else 3
        elif reps == 1:
            interval = 6 if rating != "hard" else 3
        else:
            factor = {"hard": 1.2, "good": ease, "easy": ease * 1.3}[rating]
            interval = max(interval + 1, round(interval * factor)) if rating != "hard" else max(1, round(interval * factor))
        reps += 1
    return {"ease": round(ease, 3), "reps": reps, "interval": interval, "lapses": lapses, "due": (today + timedelta(days=interval)).isoformat()}


def preview(card: dict, today: date) -> dict[str, int]:
    """Days until the next review for each rating (shown on the buttons)."""
    return {r: schedule(card, r, today)["interval"] for r in RATINGS}
