import contextlib
import io
import math
import statistics
from datetime import date, datetime, timedelta

import pytest

from core import courses as C, feynman, llm, notes as N, progress, sample, search, sqlbox, srs
from core.store import MentorStore

TODAY = date(2026, 11, 4)


# ---------- course content is verified by running it ----------
def _run(code):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        exec(code, {})
    return buf.getvalue().strip()


def test_course_structure():
    assert len(C.COURSES) == 3 and len(C.LESSONS) == 12 and len(C.QUESTIONS) == 36 and len(C.EXERCISES) == 8
    assert len(C.QUESTIONS) == len({q["id"] for l in C.LESSONS.values() for q in l["quiz"]})
    for l in C.LESSONS.values():
        assert len(l["quiz"]) == 3 and len(l["points"]) == 3 and len(l["cards"]) >= 4 and l["body"] and l["example"]
        assert all(len(kws) >= 1 for _, kws in l["points"])
        for q in l["quiz"]:
            assert len(q["options"]) == 4 and len(set(q["options"])) == 4 and 0 <= q["answer"] < 4 and q["why"]
        assert len({f for f, _ in l["cards"]}) == len(l["cards"])


@pytest.mark.parametrize("eid", list(C.EXERCISES))
def test_every_sql_solution_runs_and_is_graded_correct(eid):
    e = C.EXERCISES[eid]
    assert sqlbox.grade(e["solution"], e["solution"], e["ordered"])["ok"]
    assert sqlbox.run_query(e["solution"])["rows"]  # no exercise has an empty answer


def test_sql_solutions_have_expected_values():
    q = lambda eid: sqlbox.run_query(C.EXERCISES[eid]["solution"])["rows"]
    assert q("sql-1-e1") == [["Dev"], ["Gita"]] and [r[0] for r in q("sql-1-e2")] == [7, 11, 1]
    assert q("sql-2-e1") == [[9, 7625.0]] and sorted(r[0] for r in q("sql-2-e2")) == [1, 2, 5]
    assert dict(map(tuple, q("sql-3-e1")))["Hari"] == 0 and q("sql-3-e2") == [["Hari"]]


@pytest.mark.parametrize("qid", [k for k, q in C.QUESTIONS.items() if q["run"]])
def test_code_quiz_answers_match_real_output(qid):
    q = C.QUESTIONS[qid]
    assert _run(q["code"]) == q["options"][q["answer"]]


@pytest.mark.parametrize("qid", [k for k, q in C.QUESTIONS.items() if q["verify"]])
def test_numeric_quiz_answers_are_correct(qid):
    q = C.QUESTIONS[qid]
    assert eval(q["verify"][0], {"statistics": statistics, "math": math}) == pytest.approx(float(q["options"][q["answer"]]))


def test_python_examples_produce_the_values_the_lessons_state():
    assert _run(C.LESSONS["py-1"]["example"]).splitlines() == ["Asha scored 92.5%", "<class 'float'>", "3 1"]
    assert _run(C.LESSONS["py-2"]["example"]) == "85.0" and _run(C.LESSONS["py-3"]["example"]) == "4.0 [0, 4, 16]"
    assert _run(C.LESSONS["py-4"]["example"]) == "{'Hyd': 15, 'Mum': 20}"
    assert _run(C.LESSONS["st-1"]["example"]) == "5 4.5 4 2.0" and _run(C.LESSONS["st-2"]["example"]) == "1.5"
    assert _run(C.LESSONS["st-3"]["example"]) == "1.0 48.04 51.96"
    assert _run(C.LESSONS["st-4"]["example"]) == "1.43 0.15"  # the A/B example quoted in the lesson text
    assert "p of about 0.15" in C.LESSONS["st-4"]["body"]


# ---------- SQL sandbox ----------
@pytest.mark.parametrize("bad", ["DROP TABLE orders", "DELETE FROM orders", "UPDATE orders SET amount=0", "INSERT INTO orders VALUES (1,1,'x',1,'y')",
                                 "PRAGMA table_info(orders)", "SELECT 1; DROP TABLE orders", "ATTACH DATABASE 'x.db' AS x", "", "   ", "-- just a comment"])
def test_sandbox_rejects_unsafe_or_empty_sql(bad):
    with pytest.raises(sqlbox.SqlError):
        sqlbox.run_query(bad)


def test_sandbox_blocks_writes_hidden_inside_with_and_stays_clean():
    with pytest.raises(sqlbox.SqlError):
        sqlbox.run_query("WITH x AS (SELECT 1) DELETE FROM orders")
    assert sqlbox.run_query("SELECT COUNT(*) FROM orders")["rows"] == [[12]]  # every run starts from a fresh database


def test_sandbox_helpful_errors_limits_and_comments():
    with pytest.raises(sqlbox.SqlError, match="no such table"):
        sqlbox.run_query("SELECT * FROM nope")
    with pytest.raises(sqlbox.SqlError, match="too long"):
        sqlbox.run_query("WITH RECURSIVE r(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM r) SELECT COUNT(*) FROM r")
    big = sqlbox.run_query("WITH RECURSIVE r(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM r WHERE n<500) SELECT n FROM r")
    assert len(big["rows"]) == 200 and big["truncated"]
    assert sqlbox.run_query("SELECT 'a;b' AS x; -- trailing comment")["rows"] == [["a;b"]]


def test_grading_messages():
    sol = "SELECT name FROM customers WHERE city='Delhi' ORDER BY name"
    g = lambda sql, ordered=True: sqlbox.grade(sql, sol, ordered)
    assert g("select name from customers where city = 'Delhi' order by name desc", ordered=False)["ok"]  # order ignored when not required
    assert "wrong order" in g("SELECT name FROM customers WHERE city='Delhi' ORDER BY name DESC")["message"]
    assert "1 row(s) but 2" in g("SELECT name FROM customers WHERE city='Delhi' LIMIT 1")["message"]
    assert "column" in g("SELECT name, city FROM customers WHERE city='Delhi' ORDER BY name")["message"]
    assert "values differ" in g("SELECT name FROM customers WHERE city='Mumbai' ORDER BY name")["message"]
    assert sqlbox.grade("SELECT ROUND(1200.004, 2)", "SELECT 1200.0", False)["ok"]


# ---------- spaced repetition ----------
def test_srs_progression_and_failure():
    c = {"ease": 2.5, "reps": 0, "interval": 0, "lapses": 0}
    seen = []
    for _ in range(4):
        n = srs.schedule(c, "good", TODAY)
        seen.append(n["interval"])
        c = {**c, **n}
    assert seen[:2] == [1, 6] and seen[2] > 6 and seen[3] > seen[2]
    lapse = srs.schedule(c, "again", TODAY)
    assert lapse["interval"] == 1 and lapse["reps"] == 0 and lapse["lapses"] == 1 and lapse["ease"] < c["ease"] and lapse["due"] == "2026-11-05"


def test_srs_ease_floor_and_rating_order():
    c = {"ease": 1.3, "reps": 5, "interval": 20, "lapses": 0}
    assert srs.schedule(c, "again", TODAY)["ease"] == 1.3 and srs.schedule(c, "hard", TODAY)["ease"] == 1.3
    p = srs.preview({"ease": 2.5, "reps": 3, "interval": 10, "lapses": 0}, TODAY)
    assert p["again"] < p["hard"] < p["good"] < p["easy"] and p["again"] == 1


# ---------- store ----------
@pytest.fixture
def store(tmp_path):
    return MentorStore(tmp_path / "m.db")


def test_cards_dedupe_validation_and_decks(store):
    a = store.add_card("SQL", " What is X? ", " Y ")
    assert a and store.add_card("SQL", "What is X?", "other") is None and store.add_card("Python", "What is X?", "Z")
    assert store.decks() == ["Python", "SQL"] and store.get_card(a)["front"] == "What is X?"
    for front, back in (("", "x"), ("x", "  ")):
        with pytest.raises(ValueError):
            store.add_card("D", front, back)
    store.delete_card(a)
    assert store.get_card(a) is None


def test_due_queue_new_limit_and_review_flow(store):
    ids = [store.add_card("D", f"Q{i}", f"A{i}") for i in range(5)]
    assert [c["id"] for c in store.due_cards(TODAY, new_limit=3)] == ids[:3]
    new = store.review(ids[0], "good", TODAY, datetime(2026, 11, 4, 9))
    assert new["interval"] == 1 and store.get_card(ids[0])["due"] == "2026-11-05"
    queue = store.due_cards(TODAY, new_limit=3)
    assert ids[0] not in [c["id"] for c in queue] and len(queue) == 2  # one of today's 3 new cards is already used
    assert [c["id"] for c in store.due_cards(date(2026, 11, 5), new_limit=3)][0] == ids[0]  # due again tomorrow, before new cards
    assert store.due_cards(TODAY, new_limit=0) == [] and store.next_due(TODAY) == "2026-11-05"
    assert store.due_cards(TODAY, deck="Other") == []
    with pytest.raises(KeyError):
        store.review(999, "good")


def test_stats_retention_streak_and_activity(store):
    a, b = store.add_card("D", "a", "1"), store.add_card("D", "b", "2")
    for ago, rating in ((3, "good"), (2, "good"), (1, "again"), (0, "easy")):
        d = TODAY - timedelta(days=ago)
        store.review(a, rating, d, datetime.combine(d, datetime.min.time()).replace(hour=10))
    s = store.card_stats(TODAY)
    assert s["total"] == 2 and s["new"] == 1 and store.streak(TODAY) == 4 and store.retention(TODAY) == 75
    per = dict(store.reviews_per_day(TODAY, 5))
    assert per[TODAY] == 1 and per[TODAY - timedelta(days=1)] == 1 and per[TODAY - timedelta(days=4)] == 0
    assert store.streak(TODAY + timedelta(days=3)) == 0 and store.retention(TODAY + timedelta(days=90)) is None


def test_lessons_quiz_exercises_and_qstats(store):
    store.set_lesson("sql-1", "in_progress", 0.33)
    store.set_lesson("sql-1", "done")  # score is kept when not supplied
    assert store.lessons()["sql-1"]["status"] == "done" and store.lessons()["sql-1"]["score"] == pytest.approx(0.33)
    assert store.get_lesson_status("sql-1") == "done" and store.get_lesson_status("x") is None
    store.record_attempt("sql-1", 1, 3)
    store.record_attempt("sql-1", 3, 3)
    assert store.best_quiz("sql-1") == 1.0 and store.best_quiz("none") is None
    store.record_answer("q1", True)
    store.record_answer("q1", False)
    assert store.qstats()["q1"]["attempts"] == 2 and store.qstats()["q1"]["correct"] == 1
    store.record_exercise("e1", False)
    store.record_exercise("e1", True)
    store.record_exercise("e1", False)
    assert store.exercises_passed() == {"e1"}  # a later failure never un-passes it


def test_notes_and_reset(store):
    nid = store.save_note("T", "Some notes here")
    assert store.notes()[0]["id"] == nid and store.notes()[0]["title"] == "T"
    with pytest.raises(ValueError):
        store.save_note("x", "  ")
    store.delete_note(nid)
    store.add_card("D", "a", "b")
    store.reset()
    assert store.notes() == [] and store.cards() == [] and store.streak(TODAY) == 0


def test_demo_data(store):
    n = sample.load_demo(store, TODAY)
    assert n == 13 and store.card_stats(TODAY)["total"] == 13 and store.streak(TODAY) >= 3
    assert store.lessons()["sql-1"]["status"] == "done" and store.lessons()["py-1"]["status"] == "in_progress"
    assert sample.load_demo(store, TODAY) == 0  # loading twice does not duplicate cards


# ---------- mastery ----------
def test_mastery_weights():
    assert progress.lesson_mastery(None, 0, 4, 0, 0) == 0
    assert progress.lesson_mastery(1.0, 4, 4, 0, 0) == 100
    assert progress.lesson_mastery(1.0, 0, 4, 0, 0) == 62  # 0.5 / 0.8 of the weight when no exercises exist
    assert progress.lesson_mastery(1.0, 4, 4, 2, 2) == 100 and progress.lesson_mastery(0.5, 0, 4, 2, 2) == 45


# ---------- notes -> study material ----------
NOTES = ("Spaced repetition is a learning technique that schedules reviews at increasing intervals. The forgetting curve describes how memory fades over time without review.\n"
         "Active recall means testing yourself instead of re-reading. Active recall strengthens memory more than passive review.\n"
         "Interleaving is the practice of mixing different topics in one study session.\n"
         "Research shows that spaced repetition and active recall together give the best long-term retention for most learners.")


def test_study_pack_from_notes():
    p = N.study_pack(NOTES)
    assert {"spaced repetition", "active recall"} <= set(p["terms"])
    fronts = {d["front"]: d["back"] for d in p["definitions"]}
    assert "What is Spaced repetition?" in fronts and fronts["What is Interleaving?"].startswith("The practice of mixing")
    assert p["cloze"] and all("_____" in c["front"] and c["back"].lower() in c["sentence"].lower() for c in p["cloze"])
    assert 1 <= len(p["summary"]) <= 3
    for m in p["mcqs"]:
        assert len(set(m["options"])) == 4 and m["options"][m["answer"]].lower() in m["why"].lower()


def test_study_pack_edge_cases():
    empty = N.study_pack("")
    assert empty["terms"] == [] and empty["cloze"] == [] and empty["definitions"] == [] and empty["mcqs"] == []
    assert N.study_pack("Too short.")["cloze"] == []
    assert N.key_terms("The **mitochondria** makes energy. Cells need energy.")[0] == "mitochondria"
    assert N.mcq_from_cloze([{"front": "A _____ b", "back": "x", "sentence": "A x b"}], ["x", "y"]) == []  # not enough distractors


# ---------- teach it back ----------
def test_feynman_scoring():
    pts = C.LESSONS["sql-2"]["points"]
    good = ("Aggregates like COUNT and SUM summarise many rows into one value. GROUP BY splits the rows into groups, for example by city. "
            "WHERE filters before grouping and HAVING filters after. It is like sorting socks into piles and then counting each pile.")
    g, weak = feynman.check_explanation(good, pts), feynman.check_explanation("it does stuff", pts)
    assert g["score"] >= 90 and g["missing"] == [] and g["example"] and g["analogy"]
    assert weak["score"] < 30 and len(weak["missing"]) == 3 and any("Too short" in t for t in weak["tips"])
    assert any("Too long" in t for t in feynman.check_explanation("word " * 300, pts)["tips"])
    assert feynman.check_explanation("", [])["score"] == 0


# ---------- search ----------
def test_search_finds_the_right_lesson():
    docs = search.lesson_docs()
    assert search.search("difference between WHERE and HAVING", docs, 1)[0]["ref"] == "sql-2"
    assert search.search("what is a z-score", docs, 1)[0]["ref"] == "st-2"
    assert search.search("left join null", docs, 1)[0]["ref"] == "sql-3"
    assert search.search("the a of", docs) == [] and search.search("quantum chromodynamics", docs) == [] and search.search("x", []) == []
    mine = search.note_docs([{"id": 7, "title": "Cooking", "text": "Caramelisation happens when sugar is heated above 170 degrees until it browns."}])
    assert search.search("caramelisation sugar", docs + mine, 1)[0]["source"] == "note"


# ---------- llm normalizers ----------
def test_llm_normalizers():
    assert llm.parse_json('x {"a": 1} y') == {"a": 1}
    with pytest.raises(ValueError):
        llm.parse_json("none")
    assert llm.normalize_answer({"answer": " x ", "cited": [1, "2", 9, "z", 1]}, 3) == {"answer": "x", "cited": [1, 2]}
    cards = llm.normalize_cards({"cards": [{"front": "Q", "back": "A"}, {"front": "q", "back": "dup"}, {"front": "", "back": "x"}, "bad"]})
    assert [c["front"] for c in cards] == ["Q"] and llm.normalize_cards({"cards": "no"}) == []
    assert llm.normalize_critique({"feedback": " ok ", "correct": "x", "improve": ["a", ""]}) == {"feedback": "ok", "correct": [], "misconceptions": [], "improve": ["a"]}
    assert llm.normalize_explain({"explanation": " e "})["explanation"] == "e"
