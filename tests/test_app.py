from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from core import llm
from core.courses import LESSONS
from core.store import MentorStore

APP = str(Path(__file__).resolve().parent.parent / "app.py")
NOTES = ("Spaced repetition is a learning technique that schedules reviews at increasing intervals. The forgetting curve describes how memory fades over time without review.\n"
         "Active recall means testing yourself instead of re-reading. Active recall strengthens memory more than passive review.\n"
         "Interleaving is the practice of mixing different topics in one study session.\n"
         "Research shows that spaced repetition and active recall together give the best long-term retention for most learners.")


@pytest.fixture
def at(monkeypatch, tmp_path):
    monkeypatch.setenv("MENTOR_DB", str(tmp_path / "m.db"))
    monkeypatch.setattr(llm, "list_models", lambda host=None: [])
    app = AppTest.from_file(APP, default_timeout=60).run()
    app.store = MentorStore(tmp_path / "m.db")
    return app


def _click(app, label, sidebar=False):
    pool = app.sidebar.button if sidebar else app.button
    [b for b in pool if label in b.label][0].click().run()


def test_empty_state_is_safe(at):
    assert not at.exception and any("No flashcards yet" in i.value for i in at.info)


def test_quiz_pass_marks_lesson_done_and_fail_does_not(at):
    for q in LESSONS["sql-1"]["quiz"]:
        at.radio(key=f"ans_{q['id']}").set_value(q["answer"]).run()
    _click(at, "Check answers")
    assert not at.exception and at.store.lessons()["sql-1"]["status"] == "done" and at.store.best_quiz("sql-1") == 1.0
    assert any("Lesson complete" in m.value for m in at.markdown)
    _click(at, "Try again")
    for q in LESSONS["sql-1"]["quiz"]:
        at.radio(key=f"ans_{q['id']}").set_value((q["answer"] + 1) % 4).run()
    _click(at, "Check answers")
    assert at.store.lessons()["sql-1"]["status"] == "done"  # a bad retake never un-completes a lesson
    assert at.store.best_quiz("sql-1") == 1.0 and at.store.qstats()["sql-1-q1"]["attempts"] == 2


def test_quiz_requires_all_answers(at):
    at.radio(key="ans_sql-1-q1").set_value(0).run()
    _click(at, "Check answers")
    assert at.store.lessons() == {} and at.store.best_quiz("sql-1") is None  # nothing is recorded until every question is answered


def test_sql_sandbox_run_check_and_errors(at):
    at.text_area(key="sql_sql-1-e1").set_value("SELECT name FROM customers WHERE city = 'Delhi' ORDER BY name").run()
    [b for b in at.button if b.key == "chk_sql-1-e1"][0].click().run()
    out = at.session_state["sql_out"]["sql-1-e1"]
    assert not at.exception and out["ok"] is True and "sql-1-e1" in at.store.exercises_passed()
    at.text_area(key="sql_sql-1-e2").set_value("DROP TABLE orders").run()
    [b for b in at.button if b.key == "run_sql-1-e2"][0].click().run()
    assert at.session_state["sql_out"]["sql-1-e2"]["result"] is None and "Only SELECT" in at.session_state["sql_out"]["sql-1-e2"]["msg"]
    at.text_area(key="sql_sql-1-e2").set_value("SELECT id FROM orders ORDER BY amount LIMIT 3").run()
    [b for b in at.button if b.key == "chk_sql-1-e2"][0].click().run()
    assert at.session_state["sql_out"]["sql-1-e2"]["ok"] is False and "sql-1-e2" not in at.store.exercises_passed()


def test_flashcards_review_flow(at):
    _click(at, "Add this lesson's flashcards")
    assert len(at.store.cards()) == 5
    _click(at, "Add this lesson's flashcards")
    assert len(at.store.cards()) == 5  # idempotent
    _click(at, "Show answer")
    assert any(b.label.startswith("Good (") for b in at.button)
    _click(at, "Good (")
    assert not at.exception and at.store.card_stats(__import__("datetime").date.today())["new"] == 4
    assert at.session_state["show_back"] is False
    assert len([r for r in at.store.cards() if r["reps"] == 1]) == 1


def test_custom_card_and_duplicates(at):
    at.text_input(key="nc_front").set_value("What is a CTE?")
    at.text_area(key="nc_back").set_value("A named temporary result").run()
    _click(at, "Add card")
    assert [c["front"] for c in at.store.cards()] == ["What is a CTE?"] and at.text_input(key="nc_front").value == ""
    at.text_input(key="nc_front").set_value("What is a CTE?")
    at.text_area(key="nc_back").set_value("again").run()
    _click(at, "Add card")
    assert len(at.store.cards()) == 1


def test_teach_it_back(at):
    at.text_area(key="teach_text").set_value("Aggregates summarise rows. GROUP BY makes groups, for example per city. WHERE filters before and HAVING after grouping, like a sieve.").run()
    _click(at, "Check my explanation")
    assert not at.exception and at.session_state["teach_result"]["score"] > 40 and at.store.streak(__import__("datetime").date.today()) == 1


def test_notes_to_cards_and_ask(at):
    at.text_input(key="notes_title").set_value("Study skills")
    at.text_area(key="notes_text").set_value(NOTES).run()
    _click(at, "Generate study material")
    assert not at.exception and len(at.session_state["pack"]["cards"]) >= 3
    _click(at, "Add selected cards")
    assert len(at.store.cards()) >= 3 and {c["deck"] for c in at.store.cards()} == {"Study skills"}
    _click(at, "Save notes for Q&A")
    at.text_input(key="ask_q").set_value("what is active recall").run()
    hits = at.session_state["ask_result"]["hits"]
    assert hits and hits[0]["source"] == "note"
    at.text_input(key="ask_q").set_value("difference between WHERE and HAVING").run()
    assert at.session_state["ask_result"]["hits"][0]["ref"] == "sql-2"


def test_short_notes_rejected(at):
    at.text_area(key="notes_text").set_value("too short").run()
    _click(at, "Generate study material")
    assert at.session_state["pack"] is None and not at.exception


def test_demo_progress_and_reset(at):
    _click(at, "Load demo progress", sidebar=True)
    assert not at.exception
    m = {x.label: x.value for x in at.metric}
    assert m["Lessons completed"] == "2/12" and int(m["Cards due today"]) >= 1 and m["Study streak"] != "0 days"
    _click(at, "Delete ALL my progress", sidebar=True)
    assert at.store.cards() == [] and not at.exception


def test_ai_failure_falls_back(monkeypatch, tmp_path):
    monkeypatch.setenv("MENTOR_DB", str(tmp_path / "m.db"))
    monkeypatch.setattr(llm, "list_models", lambda host=None: ["m:latest"])

    def boom(*a, **k):
        raise ConnectionError("down")
    for fn in ("explain", "critique", "answer", "cards_from_notes"):
        monkeypatch.setattr(llm, fn, boom)
    app = AppTest.from_file(APP, default_timeout=60).run()
    _click(app, "Explain with AI")
    app.text_area(key="teach_text").set_value("Aggregates summarise many rows, for example COUNT and SUM. GROUP BY makes groups. WHERE filters before and HAVING after.").run()
    _click(app, "Check my explanation")
    assert not app.exception and app.session_state["teach_result"]["ai"] is None and app.session_state["teach_result"]["score"] > 0
    app.text_area(key="notes_text").set_value(NOTES).run()
    _click(app, "Generate study material")
    assert not app.exception and app.session_state["pack"]["cards"]
    app.text_input(key="ask_q").set_value("what is HAVING").run()
    assert not app.exception and app.session_state["ask_result"]["ai"] is None and app.session_state["ask_result"]["hits"]
