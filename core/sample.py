"""Demo progress so the dashboard has something to show."""
from datetime import date, datetime, timedelta

from .courses import COURSES, LESSONS
from .store import MentorStore

RATINGS = ["good", "good", "hard", "easy", "again"]


def load_demo(store: MentorStore, today: date) -> int:
    n = 0
    for lid in ("sql-1", "sql-2", "py-1"):
        course = COURSES[LESSONS[lid]["course"]]["title"]
        for front, back in LESSONS[lid]["cards"]:
            n += store.add_card(course, front, back, "lesson", lid) is not None
    for card in store.cards():
        for ago in (9, 6, 3, 1):
            day = today - timedelta(days=ago)
            store.review(card["id"], RATINGS[(card["id"] + ago) % 5], today=day, now=datetime.combine(day, datetime.min.time()).replace(hour=18))
    for lid, correct, total in (("sql-1", 3, 3), ("sql-2", 2, 3), ("py-1", 1, 3)):
        when = datetime.combine(today - timedelta(days=2), datetime.min.time()).replace(hour=19)
        store.record_attempt(lid, correct, total, when)
        store.set_lesson(lid, "done" if correct / total >= 2 / 3 else "in_progress", correct / total)
    store.record_exercise("sql-1-e1", True)
    store.record_answer("py-1-q1", False)
    store.record_answer("py-1-q1", False)
    store.record_answer("sql-2-q3", False)
    store.log_activity("quiz", "demo")
    return n
