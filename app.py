import inspect
import os
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from core import feynman, llm, notes as notes_mod, progress, sample, search, sqlbox, srs
from core.courses import COURSES, EXERCISES, LESSONS, QUESTIONS, SQL_SCHEMA
from core.store import MentorStore

# Streamlit 1.50+ replaced use_container_width with width="stretch"; support both.
STRETCH = {"width": "stretch"} if "width" in inspect.signature(st.button).parameters else {"use_container_width": True}
st.set_page_config(page_title="AI Learning Mentor", page_icon="🎓", layout="wide")
DB_PATH = Path(os.environ.get("MENTOR_DB", Path(__file__).parent / "data" / "mentor.db"))
store = MentorStore(DB_PATH)
TODAY = date.today()
ss = st.session_state
for k, v in {"flash": "", "quiz_result": {}, "sql_out": {}, "show_back": False, "teach_result": None, "pack": None, "pack_quiz": None, "ask_result": None,
             "explain_out": None, "new_limit": 10, "ask_q": "", "notes_text": "", "notes_title": "", "teach_text": "", "ver": 0}.items():
    ss.setdefault(k, v)
ICON = {"done": "✅", "in_progress": "🟡"}


# ---------- callbacks ----------
def add_lesson_cards_cb(lid):
    l = LESSONS[lid]
    n = sum(store.add_card(COURSES[l["course"]]["title"], f, b, "lesson", lid) is not None for f, b in l["cards"])
    ss.flash = f"Added {n} new flashcard(s)." if n else "Those flashcards are already in your deck."


def quiz_cb(lid):
    l = LESSONS[lid]
    chosen = [ss.get(f"ans_{q['id']}") for q in l["quiz"]]
    if any(c is None for c in chosen):
        ss.flash = "Answer every question first."
        return
    correct = [c == q["answer"] for c, q in zip(chosen, l["quiz"])]
    store.record_attempt(lid, sum(correct), len(correct))
    for q, ok in zip(l["quiz"], correct):
        store.record_answer(q["id"], ok)
    best = store.best_quiz(lid) or 0.0  # a worse retake never un-completes a lesson
    store.set_lesson(lid, "done" if best >= 2 / 3 else "in_progress", best)
    ss.quiz_result[lid] = {"chosen": chosen, "correct": correct}


def retry_cb(lid):
    for q in LESSONS[lid]["quiz"]:
        ss.pop(f"ans_{q['id']}", None)
    ss.quiz_result.pop(lid, None)


def sql_cb(eid, check):
    e = EXERCISES[eid]
    sql = ss.get(f"sql_{eid}", "")
    try:
        if check:
            r = sqlbox.grade(sql, e["solution"], e["ordered"])
            store.record_exercise(eid, r["ok"])
            if r["ok"] and store.get_lesson_status(e["lesson"]) is None:
                store.set_lesson(e["lesson"], "in_progress")
            ss.sql_out[eid] = {"ok": r["ok"], "msg": r["message"], "result": r["result"]}
        else:
            ss.sql_out[eid] = {"ok": None, "msg": "", "result": sqlbox.run_query(sql)}
    except sqlbox.SqlError as ex:
        ss.sql_out[eid] = {"ok": False, "msg": str(ex), "result": None}


def explain_cb(lid):
    l = LESSONS[lid]
    try:
        ss.explain_out = {"lid": lid, **llm.explain(l["title"], l["body"], ss.explain_style, ss.get("model", "llama3.2"), ss.get("host"))}
    except Exception as ex:
        ss.flash = f"AI unavailable ({ex}). Use the quick recap instead."


def rate_cb(card_id, rating):
    store.review(card_id, rating, TODAY)
    ss.show_back = False


def add_card_cb():
    try:
        ok = store.add_card(ss.nc_deck, ss.nc_front, ss.nc_back, "manual")
        ss.flash = "Card added." if ok else "That card already exists in the deck."
        if ok:
            ss.nc_front = ss.nc_back = ""
    except ValueError as ex:
        ss.flash = str(ex)


def teach_cb(lid):
    l = LESSONS[lid]
    text = ss.teach_text.strip()
    if not text:
        ss.flash = "Write your explanation first."
        return
    res = feynman.check_explanation(text, l["points"])
    res["ai"] = None
    if ss.get("use_ai"):
        try:
            res["ai"] = llm.critique(l["title"], [p for p, _ in l["points"]], text, ss.get("model", "llama3.2"), ss.get("host"))
        except Exception as ex:
            ss.flash = f"AI feedback unavailable ({ex}). Showing the offline check."
    res["lid"] = lid
    ss.teach_result = res
    store.log_activity("teach", lid)


def analyze_notes_cb():
    text = ss.notes_text.strip()
    if len(text.split()) < 20:
        ss.flash = "Paste at least a few sentences of notes."
        return
    pack = notes_mod.study_pack(text)
    ai_cards = []
    if ss.get("use_ai"):
        try:
            ai_cards = llm.cards_from_notes(text, ss.get("model", "llama3.2"), ss.get("host"))
        except Exception as ex:
            ss.flash = f"AI unavailable ({ex}). Used the offline generator."
    pack["cards"] = pack["definitions"] + pack["cloze"] + ai_cards
    ss.pack, ss.pack_quiz = pack, None
    ss.ver += 1
    for i in range(len(pack["mcqs"])):
        ss.pop(f"nq_{i}", None)


def add_pack_cards_cb():
    deck = (ss.pack_deck or "Notes").strip()
    edited = ss.pack_cards_live
    n = 0
    for _, r in edited.iterrows():
        if r["add"] and str(r["front"]).strip() and str(r["back"]).strip():
            n += store.add_card(deck, r["front"], r["back"], "notes") is not None
    ss.flash = f"Added {n} card(s) to '{deck}'."


def save_notes_cb():
    store.save_note(ss.notes_title or "My notes", ss.notes_text)
    ss.flash = "Notes saved. You can now ask questions about them in the Ask tab."


def check_pack_quiz_cb():
    pack = ss.pack
    chosen = [ss.get(f"nq_{i}") for i in range(len(pack["mcqs"]))]
    if any(c is None for c in chosen):
        ss.flash = "Answer every question first."
        return
    ss.pack_quiz = [c == q["answer"] for c, q in zip(chosen, pack["mcqs"])]


def ask_cb():
    q = ss.ask_q.strip()
    ss.ask_result = None
    if not q:
        return
    docs = search.lesson_docs() + search.note_docs(store.notes())
    hits = search.search(q, docs, 4)
    res = {"q": q, "hits": hits, "ai": None}
    if ss.get("use_ai") and hits:
        try:
            res["ai"] = llm.answer(q, [h["text"] for h in hits], ss.get("model", "llama3.2"), ss.get("host"))
        except Exception as ex:
            ss.flash = f"AI unavailable ({ex}). Showing the passages found."
    ss.ask_result = res


def demo_cb():
    n = sample.load_demo(store, TODAY)
    ss.flash = f"Demo progress loaded ({n} cards)."


def reset_cb():
    store.reset()
    for k in ("quiz_result", "sql_out"):
        ss[k] = {}
    for k in [k for k in ss if str(k).startswith(("ans_", "sql_", "nq_"))]:
        del ss[k]
    ss.flash = "All progress deleted."


# ---------- sidebar ----------
with st.sidebar:
    st.header("⚙️ Settings")
    st.slider("New cards per day", 0, 30, key="new_limit")
    host = st.text_input("Ollama host", value="http://localhost:11434", key="host")
    installed = llm.list_models(host)
    if installed:
        st.selectbox("Model", installed, key="model")
        st.checkbox("Use AI features", value=True, key="use_ai")
    else:
        ss["use_ai"] = False
        st.caption("Ollama not detected. Courses, quizzes, SQL practice, flashcards and notes tools all work offline.")
    st.divider()
    st.button("Load demo progress", on_click=demo_cb, **STRETCH)
    with st.expander("Danger zone"):
        st.button("Delete ALL my progress", on_click=reset_cb)
    st.caption(f"Your progress is stored locally in {DB_PATH.name}.")

st.title("🎓 AI Learning Mentor")
if ss.flash:
    st.toast(ss.flash)
    ss.flash = ""

lesson_state = store.lessons()
stats = store.card_stats(TODAY)
t_learn, t_review, t_teach, t_notes, t_ask, t_prog = st.tabs(["📚 Learn", f"🃏 Review ({stats['due'] + min(stats['new'], max(0, ss.new_limit - store.new_introduced_today(TODAY)))})",
                                                              "🧠 Teach it back", "📝 My notes", "💬 Ask", "📊 Progress"])

# ---------- learn ----------
with t_learn:
    cid = st.selectbox("Course", list(COURSES), format_func=lambda c: f"{COURSES[c]['title']}  ({COURSES[c]['level']})", key="course")
    course = COURSES[cid]
    st.caption(course["desc"])
    ids = [l["id"] for l in course["lessons"]]
    lid = st.radio("Lessons", ids, format_func=lambda i: f"{ICON.get((lesson_state.get(i) or {}).get('status'), '○')} {LESSONS[i]['title']} ({LESSONS[i]['minutes']} min)",
                   key=f"lesson_{cid}", horizontal=False)
    lesson = LESSONS[lid]
    own_cards = store.cards(lesson_id=lid)
    best = store.best_quiz(lid)
    ex_pass = store.exercises_passed()
    mastery = progress.lesson_mastery(best, sum(1 for c in own_cards if c["interval"] >= srs.LEARNED_DAYS), len(lesson["cards"]),
                                      sum(1 for e in lesson["exercises"] if e["id"] in ex_pass), len(lesson["exercises"]))
    st.progress(mastery / 100, text=f"Mastery of this lesson: {mastery}%")
    st.header(lesson["title"])
    st.markdown(lesson["body"])
    st.code(lesson["example"], language=lesson["lang"])
    st.markdown("**Key points**")
    for p, _ in lesson["points"]:
        st.write(f"- {p}")
    b1, b2 = st.columns([1, 2])
    b1.button("🃏 Add this lesson's flashcards", on_click=add_lesson_cards_cb, args=(lid,), key=f"addc_{lid}")
    with st.expander("🔄 Explain it differently"):
        recap = "  \n".join(f"• {p}" for p, _ in lesson["points"])
        st.markdown(f"**Quick recap**  \n{recap}")
        if ss.get("use_ai"):
            st.selectbox("Style", ["Simple, like I'm new to this", "Using an everyday analogy", "Step by step", "For a data analyst"], key="explain_style")
            st.button("✨ Explain with AI", on_click=explain_cb, args=(lid,), key=f"exp_{lid}")
            out = ss.explain_out
            if out and out["lid"] == lid and out["explanation"]:
                st.info(out["explanation"])
                if out["analogy"]:
                    st.write(f"**Analogy:** {out['analogy']}")
                if out["check_question"]:
                    st.write(f"**Test yourself:** {out['check_question']}")

    st.subheader("Check your understanding")
    res = ss.quiz_result.get(lid)
    for q in lesson["quiz"]:
        st.markdown(f"**{q['q']}**")
        if q["code"]:
            st.code(q["code"], language="python")
        st.radio(q["q"], list(range(len(q["options"]))), format_func=lambda i, q=q: q["options"][i], key=f"ans_{q['id']}", index=None,
                 label_visibility="collapsed", disabled=res is not None)
        if res:
            ok = res["correct"][lesson["quiz"].index(q)]
            (st.success if ok else st.error)(("Correct. " if ok else f"Not quite. Answer: {q['options'][q['answer']]}. ") + q["why"])
    if res is None:
        st.button("Check answers", type="primary", on_click=quiz_cb, args=(lid,), key=f"qc_{lid}")
    else:
        st.write(f"**Score: {sum(res['correct'])}/{len(res['correct'])}**" + ("  ✅ Lesson complete!" if sum(res["correct"]) / len(res["correct"]) >= 2 / 3 else "  Review the lesson and try again."))
        st.button("Try again", on_click=retry_cb, args=(lid,), key=f"qr_{lid}")

    if lesson["exercises"]:
        st.subheader("Practice in the SQL sandbox")
        st.caption("Tables: " + SQL_SCHEMA.replace("\n", "  |  "))
        for e in lesson["exercises"]:
            st.markdown(f"**{e['prompt']}**")
            st.text_area("Your query", key=f"sql_{e['id']}", height=100, placeholder="SELECT ...", label_visibility="collapsed")
            c1, c2, _ = st.columns([1, 1, 4])
            c1.button("▶ Run", on_click=sql_cb, args=(e["id"], False), key=f"run_{e['id']}")
            c2.button("✓ Check", on_click=sql_cb, args=(e["id"], True), key=f"chk_{e['id']}", type="primary")
            out = ss.sql_out.get(e["id"])
            if out:
                if out["msg"]:
                    (st.success if out["ok"] else st.error)(out["msg"])
                if out["result"]:
                    st.dataframe(pd.DataFrame(out["result"]["rows"], columns=out["result"]["columns"]), hide_index=True, **STRETCH)
            with st.expander("Hint and solution"):
                st.write(f"💡 {e['hint']}")
                if e["id"] in ex_pass or st.checkbox("Show the solution", key=f"sol_{e['id']}"):
                    st.code(e["solution"], language="sql")

# ---------- review ----------
with t_review:
    decks = store.decks()
    deck_f = st.selectbox("Deck", ["All decks"] + decks, key="deck_f")
    queue = store.due_cards(TODAY, ss.new_limit, None if deck_f == "All decks" else deck_f)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Due now", len(queue))
    m2.metric("Cards in total", stats["total"])
    m3.metric("Learned (7+ day interval)", stats["learned"])
    ret = store.retention(TODAY)
    m4.metric("Retention (30 days)", f"{ret}%" if ret is not None else "n/a")
    if not stats["total"]:
        st.info("No flashcards yet. Open a lesson and click **Add this lesson's flashcards**, or create your own below.")
    elif not queue:
        nd = store.next_due(TODAY)
        st.success("🎉 All caught up for today!" + (f" Next review: {nd}." if nd else ""))
    else:
        card = queue[0]
        st.progress(0.0, text=f"{len(queue)} card(s) left · {card['deck']}")
        st.markdown(f"### {card['front']}")
        if not ss.show_back:
            st.button("Show answer", type="primary", on_click=lambda: ss.update(show_back=True), key="show_ans")
        else:
            st.markdown(f"**{card['back']}**")
            prev = srs.preview(card, TODAY)
            cols = st.columns(4)
            for col, (r, label) in zip(cols, (("again", "Again"), ("hard", "Hard"), ("good", "Good"), ("easy", "Easy"))):
                col.button(f"{label} ({prev[r]}d)", on_click=rate_cb, args=(card["id"], r), key=f"rate_{r}", **STRETCH)
            st.caption("Again = forgot, Hard = recalled with effort, Good = recalled, Easy = effortless. Cards you rate Again come back tomorrow.")
    with st.expander("➕ Add your own card"):
        st.text_input("Deck", value="My cards", key="nc_deck")
        st.text_input("Front (question)", key="nc_front")
        st.text_area("Back (answer)", key="nc_back", height=80)
        st.button("Add card", on_click=add_card_cb)
    with st.expander("Browse cards"):
        allc = store.cards(None if deck_f == "All decks" else deck_f)
        if allc:
            st.dataframe(pd.DataFrame([{"Deck": c["deck"], "Front": c["front"], "Due": c["due"] or "new", "Interval (d)": c["interval"], "Reviews": c["reps"], "Lapses": c["lapses"]} for c in allc]),
                         hide_index=True, **STRETCH)

# ---------- teach it back ----------
with t_teach:
    st.write("Explaining an idea in your own words is one of the strongest ways to learn it. Pick a lesson and teach it as if to a friend.")
    tl = st.selectbox("Lesson", list(LESSONS), format_func=lambda i: f"{COURSES[LESSONS[i]['course']]['title']}: {LESSONS[i]['title']}", key="teach_lesson")
    st.text_area("Your explanation (40-250 words)", key="teach_text", height=180)
    st.button("Check my explanation", type="primary", on_click=teach_cb, args=(tl,))
    tr = ss.teach_result
    if tr and tr["lid"] == tl:
        st.metric("Teach-back score", f"{tr['score']}/100")
        l, r = st.columns(2)
        for x in tr["covered"]:
            l.write(f"✅ {x}")
        for x in tr["missing"]:
            r.write(f"⚠️ Missing: {x}")
        for x in tr["tips"]:
            st.write(f"💡 {x}")
        if tr["ai"] and tr["ai"]["feedback"]:
            st.info(tr["ai"]["feedback"])
            for x in tr["ai"]["misconceptions"]:
                st.write(f"❗ {x}")
            for x in tr["ai"]["improve"]:
                st.write(f"➡️ {x}")

# ---------- notes ----------
with t_notes:
    st.write("Paste any notes or article text and get key terms, a summary, flashcards and a practice quiz.")
    st.text_input("Title", key="notes_title", placeholder="e.g. Spaced repetition")
    st.text_area("Your notes", key="notes_text", height=200)
    c1, c2, _ = st.columns([1, 1, 3])
    c1.button("🔍 Generate study material", type="primary", on_click=analyze_notes_cb)
    c2.button("💾 Save notes for Q&A", on_click=save_notes_cb, disabled=not ss.notes_text.strip())
    pack = ss.pack
    if pack:
        st.markdown("**Key terms:** " + (", ".join(f"`{t}`" for t in pack["terms"]) or "none found (try longer notes)"))
        if pack["summary"]:
            st.markdown("**Summary**")
            for s_ in pack["summary"]:
                st.write(f"- {s_}")
        if pack["cards"]:
            st.markdown("**Suggested flashcards** (untick any you do not want)")
            df = pd.DataFrame([{"add": True, "front": c["front"], "back": c["back"], "type": c["kind"]} for c in pack["cards"]])
            ss.pack_cards_live = st.data_editor(df, hide_index=True, **STRETCH, disabled=["type"], key=f"pack_{ss.ver}",
                                                column_config={"add": st.column_config.CheckboxColumn("Add?"), "front": st.column_config.TextColumn(width="large"), "back": st.column_config.TextColumn(width="large")})
            st.text_input("Add to deck", value=ss.notes_title or "Notes", key="pack_deck")
            st.button("➕ Add selected cards", on_click=add_pack_cards_cb)
        else:
            st.info("Not enough definitions or key sentences found. Try pasting a longer, explanatory text.")
        if pack["mcqs"]:
            st.markdown("**Practice quiz**")
            for i, q in enumerate(pack["mcqs"]):
                st.markdown(q["q"])
                st.radio(q["q"], range(len(q["options"])), format_func=lambda j, q=q: q["options"][j], key=f"nq_{i}", index=None, label_visibility="collapsed", disabled=ss.pack_quiz is not None)
            if ss.pack_quiz is None:
                st.button("Check quiz", on_click=check_pack_quiz_cb)
            else:
                st.success(f"Score: {sum(ss.pack_quiz)}/{len(ss.pack_quiz)}")
    saved = store.notes()
    if saved:
        with st.expander(f"Saved notes ({len(saved)})"):
            for n in saved:
                a, b = st.columns([5, 1])
                a.write(f"**{n['title']}**  ·  {len(n['text'].split())} words")
                b.button("Delete", key=f"dn_{n['id']}", on_click=store.delete_note, args=(n["id"],))

# ---------- ask ----------
with t_ask:
    st.text_input("Ask the mentor", key="ask_q", on_change=ask_cb, placeholder="What is the difference between WHERE and HAVING?   (press Enter)")
    st.caption("Searches the built-in lessons and your saved notes.")
    res = ss.ask_result
    if res:
        if res["ai"] and res["ai"]["answer"]:
            st.success(res["ai"]["answer"])
        if res["hits"]:
            st.markdown("**Relevant passages**")
            for n, h in enumerate(res["hits"], 1):
                st.markdown(f"**[{n}] {h['title']}** · {'lesson' if h['source'] == 'lesson' else 'your notes'}")
                st.write(h["text"])
        else:
            st.info("Nothing relevant found. Try different keywords, or save more notes.")

# ---------- progress ----------
with t_prog:
    done = [i for i, v in lesson_state.items() if v["status"] == "done"]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Lessons completed", f"{len(done)}/{len(LESSONS)}")
    m2.metric("Study streak", f"{store.streak(TODAY)} days")
    m3.metric("Cards due today", stats["due"])
    m4.metric("Cards learned", f"{stats['learned']}/{stats['total']}")
    rows = []
    for lid_, l in LESSONS.items():
        cs = store.cards(lesson_id=lid_)
        mastery_ = progress.lesson_mastery(store.best_quiz(lid_), sum(1 for c in cs if c["interval"] >= srs.LEARNED_DAYS), len(l["cards"]),
                                           sum(1 for e in l["exercises"] if e["id"] in store.exercises_passed()), len(l["exercises"]))
        rows.append({"Course": COURSES[l["course"]]["title"], "Lesson": l["title"], "Status": (lesson_state.get(lid_) or {}).get("status", "not started"), "Mastery %": mastery_, "id": lid_})
    df = pd.DataFrame(rows)
    nxt = next((r for r in rows if r["Status"] != "done"), None)
    weak = sorted((r for r in rows if r["Status"] != "not started" and r["Mastery %"] < 60), key=lambda r: r["Mastery %"])
    st.markdown("**What to do next**")
    st.write(f"- Review your {stats['due']} due card(s)." if stats["due"] else "- No cards due. Nice.")
    if nxt:
        st.write(f"- Continue with **{nxt['Lesson']}** ({nxt['Course']}).")
    if weak:
        st.write(f"- Strengthen **{weak[0]['Lesson']}** (mastery {weak[0]['Mastery %']}%): retake the quiz or review its flashcards.")
    st.markdown("**Reviews per day (14 days)**")
    st.bar_chart(pd.Series({d.strftime("%d %b"): n for d, n in store.reviews_per_day(TODAY)}, name="reviews"))
    st.markdown("**Mastery by lesson**")
    st.dataframe(df.drop(columns="id"), hide_index=True, **STRETCH)
    qs = store.qstats()
    shaky = sorted(((v["correct"] / v["attempts"], k) for k, v in qs.items() if v["attempts"] and k in QUESTIONS and v["correct"] / v["attempts"] < 0.7))
    if shaky:
        st.markdown("**Questions you often miss**")
        for acc, k in shaky[:6]:
            st.write(f"- {QUESTIONS[k]['q']}  ({round(acc * 100)}% correct) · *{LESSONS[QUESTIONS[k]['lesson']]['title']}*")
