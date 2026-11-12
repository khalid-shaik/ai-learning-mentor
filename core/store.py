"""SQLite storage for flashcards, reviews, lesson progress, quiz stats, activity and notes."""
import sqlite3
from contextlib import closing
from datetime import date, datetime, timedelta
from pathlib import Path

from . import srs

SCHEMA = """
CREATE TABLE IF NOT EXISTS cards (id INTEGER PRIMARY KEY AUTOINCREMENT, deck TEXT NOT NULL, front TEXT NOT NULL, back TEXT NOT NULL, source TEXT NOT NULL DEFAULT '',
  lesson_id TEXT NOT NULL DEFAULT '', created TEXT NOT NULL, ease REAL NOT NULL DEFAULT 2.5, interval INTEGER NOT NULL DEFAULT 0, reps INTEGER NOT NULL DEFAULT 0,
  lapses INTEGER NOT NULL DEFAULT 0, due TEXT, last_review TEXT, UNIQUE(deck, front));
CREATE TABLE IF NOT EXISTS reviews (id INTEGER PRIMARY KEY AUTOINCREMENT, card_id INTEGER NOT NULL, ts TEXT NOT NULL, rating TEXT NOT NULL, interval_after INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS lessons (lesson_id TEXT PRIMARY KEY, status TEXT NOT NULL, score REAL, updated TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS attempts (id INTEGER PRIMARY KEY AUTOINCREMENT, lesson_id TEXT NOT NULL, ts TEXT NOT NULL, correct INTEGER NOT NULL, total INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS qstats (qid TEXT PRIMARY KEY, attempts INTEGER NOT NULL DEFAULT 0, correct INTEGER NOT NULL DEFAULT 0, last_ts TEXT);
CREATE TABLE IF NOT EXISTS exercises (eid TEXT PRIMARY KEY, passed INTEGER NOT NULL DEFAULT 0, tries INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS activity (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, day TEXT NOT NULL, kind TEXT NOT NULL, ref TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, text TEXT NOT NULL, created TEXT NOT NULL);
"""


class MentorStore:
    def __init__(self, path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with closing(self._conn()) as c:
            c.executescript(SCHEMA)
            c.commit()

    def _conn(self):
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        return c

    def _q(self, sql, args=()):
        with closing(self._conn()) as c:
            return [dict(r) for r in c.execute(sql, args)]

    def _x(self, sql, args=()):
        with closing(self._conn()) as c:
            cur = c.execute(sql, args)
            c.commit()
            return cur

    # ----- cards -----
    def add_card(self, deck, front, back, source="", lesson_id="", created=None) -> int | None:
        front, back = (front or "").strip(), (back or "").strip()
        if not front or not back:
            raise ValueError("A card needs both a front and a back.")
        with closing(self._conn()) as c:
            cur = c.execute("INSERT OR IGNORE INTO cards (deck,front,back,source,lesson_id,created) VALUES (?,?,?,?,?,?)",
                            (deck.strip() or "General", front, back, source, lesson_id, created or datetime.now().isoformat(timespec="seconds")))
            c.commit()
            return cur.lastrowid if cur.rowcount else None

    def get_card(self, card_id: int) -> dict | None:
        rows = self._q("SELECT * FROM cards WHERE id=?", (card_id,))
        return rows[0] if rows else None

    def cards(self, deck=None, lesson_id=None) -> list[dict]:
        q, args = "SELECT * FROM cards WHERE 1=1", []
        for col, val in (("deck", deck), ("lesson_id", lesson_id)):
            if val is not None:
                q, args = q + f" AND {col}=?", args + [val]
        return self._q(q + " ORDER BY id", args)

    def decks(self) -> list[str]:
        return [r["deck"] for r in self._q("SELECT DISTINCT deck FROM cards ORDER BY deck")]

    def delete_card(self, card_id: int):
        self._x("DELETE FROM cards WHERE id=?", (card_id,))
        self._x("DELETE FROM reviews WHERE card_id=?", (card_id,))

    def new_introduced_today(self, today: date) -> int:
        rows = self._q("SELECT COUNT(*) AS n FROM (SELECT card_id FROM reviews GROUP BY card_id HAVING substr(MIN(ts),1,10)=?)", (today.isoformat(),))
        return rows[0]["n"]

    def due_cards(self, today: date, new_limit: int = 10, deck: str | None = None) -> list[dict]:
        extra, args = (" AND deck=?", [deck]) if deck else ("", [])
        due = self._q("SELECT * FROM cards WHERE reps+lapses>0 AND due<=?" + extra + " ORDER BY due, id", [today.isoformat()] + args)
        slots = max(0, new_limit - self.new_introduced_today(today))
        new = self._q("SELECT * FROM cards WHERE reps+lapses=0" + extra + " ORDER BY id LIMIT ?", args + [slots])
        return due + new

    def review(self, card_id: int, rating: str, today: date | None = None, now: datetime | None = None) -> dict:
        today = today or date.today()
        now = now or datetime.now()
        card = self.get_card(card_id)
        if not card:
            raise KeyError(card_id)
        new = srs.schedule(card, rating, today)
        self._x("UPDATE cards SET ease=?, reps=?, interval=?, lapses=?, due=?, last_review=? WHERE id=?",
                (new["ease"], new["reps"], new["interval"], new["lapses"], new["due"], now.isoformat(timespec="seconds"), card_id))
        self._x("INSERT INTO reviews (card_id,ts,rating,interval_after) VALUES (?,?,?,?)", (card_id, now.isoformat(timespec="seconds"), rating, new["interval"]))
        self.log_activity("review", str(card_id), now)
        return new

    def next_due(self, today: date) -> str | None:
        r = self._q("SELECT MIN(due) AS d FROM cards WHERE reps+lapses>0 AND due>?", (today.isoformat(),))[0]["d"]
        return r

    def card_stats(self, today: date) -> dict:
        r = self._q("SELECT COUNT(*) AS total, SUM(reps+lapses=0) AS new, SUM(reps+lapses>0 AND due<=?) AS due, SUM(interval>=?) AS learned FROM cards",
                    (today.isoformat(), srs.LEARNED_DAYS))[0]
        return {k: int(v or 0) for k, v in r.items()}

    def reviews_per_day(self, today: date, days: int = 14) -> list[tuple[date, int]]:
        since = (today - timedelta(days=days - 1)).isoformat()
        counts = {r["d"]: r["n"] for r in self._q("SELECT substr(ts,1,10) AS d, COUNT(*) AS n FROM reviews WHERE substr(ts,1,10)>=? GROUP BY d", (since,))}
        return [(today - timedelta(days=i), counts.get((today - timedelta(days=i)).isoformat(), 0)) for i in range(days - 1, -1, -1)]

    def retention(self, today: date, days: int = 30) -> float | None:
        since = (today - timedelta(days=days)).isoformat()
        r = self._q("SELECT COUNT(*) AS n, SUM(rating!='again') AS ok FROM reviews WHERE substr(ts,1,10)>=?", (since,))[0]
        return round(100 * (r["ok"] or 0) / r["n"]) if r["n"] else None

    # ----- lessons, quizzes, exercises -----
    def set_lesson(self, lesson_id: str, status: str, score: float | None = None):
        self._x("INSERT INTO lessons (lesson_id,status,score,updated) VALUES (?,?,?,?) ON CONFLICT(lesson_id) DO UPDATE SET status=excluded.status, "
                "score=COALESCE(excluded.score, score), updated=excluded.updated", (lesson_id, status, score, datetime.now().isoformat(timespec="seconds")))

    def get_lesson_status(self, lesson_id: str) -> str | None:
        r = self._q("SELECT status FROM lessons WHERE lesson_id=?", (lesson_id,))
        return r[0]["status"] if r else None

    def lessons(self) -> dict:
        return {r["lesson_id"]: r for r in self._q("SELECT * FROM lessons")}

    def record_attempt(self, lesson_id: str, correct: int, total: int, when: datetime | None = None):
        when = when or datetime.now()
        self._x("INSERT INTO attempts (lesson_id,ts,correct,total) VALUES (?,?,?,?)", (lesson_id, when.isoformat(timespec="seconds"), correct, total))
        self.log_activity("quiz", lesson_id, when)

    def best_quiz(self, lesson_id: str) -> float | None:
        r = self._q("SELECT MAX(1.0*correct/total) AS b FROM attempts WHERE lesson_id=? AND total>0", (lesson_id,))[0]["b"]
        return None if r is None else float(r)

    def record_answer(self, qid: str, correct: bool):
        self._x("INSERT INTO qstats (qid,attempts,correct,last_ts) VALUES (?,1,?,?) ON CONFLICT(qid) DO UPDATE SET attempts=attempts+1, correct=correct+?, last_ts=?",
                (qid, int(correct), datetime.now().isoformat(timespec="seconds"), int(correct), datetime.now().isoformat(timespec="seconds")))

    def qstats(self) -> dict:
        return {r["qid"]: r for r in self._q("SELECT * FROM qstats")}

    def record_exercise(self, eid: str, passed: bool):
        self._x("INSERT INTO exercises (eid,passed,tries) VALUES (?,?,1) ON CONFLICT(eid) DO UPDATE SET tries=tries+1, passed=MAX(passed, excluded.passed)", (eid, int(passed)))
        self.log_activity("exercise", eid)

    def exercises_passed(self) -> set[str]:
        return {r["eid"] for r in self._q("SELECT eid FROM exercises WHERE passed=1")}

    # ----- activity -----
    def log_activity(self, kind: str, ref: str = "", when: datetime | None = None):
        when = when or datetime.now()
        self._x("INSERT INTO activity (ts,day,kind,ref) VALUES (?,?,?,?)", (when.isoformat(timespec="seconds"), when.date().isoformat(), kind, ref))

    def streak(self, today: date) -> int:
        days = {r["day"] for r in self._q("SELECT DISTINCT day FROM activity")}
        d = today if today.isoformat() in days else today - timedelta(days=1)
        n = 0
        while d.isoformat() in days:
            n += 1
            d -= timedelta(days=1)
        return n

    # ----- notes -----
    def save_note(self, title: str, text: str) -> int:
        if not text.strip():
            raise ValueError("Note is empty.")
        return self._x("INSERT INTO notes (title,text,created) VALUES (?,?,?)", (title.strip() or "Untitled notes", text.strip(), datetime.now().isoformat(timespec="seconds"))).lastrowid

    def notes(self) -> list[dict]:
        return self._q("SELECT * FROM notes ORDER BY id DESC")

    def delete_note(self, note_id: int):
        self._x("DELETE FROM notes WHERE id=?", (note_id,))

    def reset(self):
        for t in ("cards", "reviews", "lessons", "attempts", "qstats", "exercises", "activity", "notes"):
            self._x(f"DELETE FROM {t}")
