# 🎓 AI Learning Mentor

**Project 9 of 60 AI agents.** A personal tutor that teaches, tests and remembers. It combines short lessons, auto-graded practice, spaced-repetition flashcards, a "teach it back" checker and a search over your own notes. It runs locally and **works fully offline**; Ollama only adds re-explanations, feedback and answers.

## What is inside
- **3 built-in courses (12 lessons):** SQL Fundamentals, Python for Data, Statistics Essentials. Every code sample, SQL solution and numeric quiz answer is **checked by the test suite**, so the content can be trusted
- **Live SQL sandbox:** write queries against a practice database and get them graded by comparing results (not text). It is read-only, one statement at a time, with a time limit
- **Quizzes:** 3 questions per lesson with explanations. Passing (2/3) completes the lesson, and a worse retake never undoes it
- **Spaced repetition (SM-2 style):** flashcards from lessons, your own cards or your notes. Buttons show the next interval (Again, Hard, Good, Easy). New cards per day are capped
- **Teach it back (Feynman):** explain a lesson in your own words and get a score for coverage of the key ideas, examples and analogies, plus what you missed
- **My notes:** paste any text to get key terms, a summary, suggested definition and fill-in-the-blank flashcards, and a practice quiz. Save notes so you can ask questions about them
- **Ask:** BM25 search across lessons and your notes, with optional AI answers that cite passages
- **Progress:** mastery per lesson (quiz 50%, retained cards 30%, exercises 20%), streak, retention, reviews per day, questions you often miss and what to do next

## Tech stack
Python · Streamlit · SQLite · pandas · Ollama (optional) · pytest · GitHub Actions

## Quick start
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```
Click **Load demo progress** in the sidebar to see a populated dashboard, or just start with **SQL Fundamentals → lesson 1**. For AI features install Ollama and run `ollama pull llama3.2`.

## A good daily routine (15 to 20 minutes)
1. **Review** your due flashcards (Review tab)
2. Do **one lesson**: read, add its flashcards, take the quiz
3. **Teach it back** once a week for the lesson you feel least sure about
4. Paste notes from anything else you study and turn them into cards

## Project structure
```
app.py             Streamlit UI (6 tabs)
core/courses.py    3 courses, 12 lessons, 36 quiz questions, 8 SQL exercises
core/sqlbox.py     safe in-memory SQL sandbox and grader
core/srs.py        spaced-repetition scheduling
core/store.py      SQLite: cards, reviews, lesson progress, quiz stats, activity, notes
core/progress.py   mastery calculation
core/notes.py      notes -> key terms, summary, flashcards, quiz
core/feynman.py    teach-it-back scoring
core/search.py     BM25 search over lessons and notes
core/llm.py        optional Ollama helpers (validated JSON)
core/sample.py     demo progress
tests/             60 pytest unit and UI tests
data/              your progress database (git-ignored)
```

## Limits
- The built-in courses cover the basics of three topics. Use **My notes** for everything else.
- Notes-to-cards is rule-based offline (definitions and fill-in-the-blanks). It works best on clear explanatory text. With Ollama it also asks the model for question-and-answer cards.
- Teach-back scoring checks coverage of key ideas by keywords, so it cannot judge whether an explanation is truly correct. The optional AI feedback helps with that.
- A card rated "Again" returns tomorrow rather than later in the same session.

## Tests
```bash
pytest -q
```

## Roadmap
- [ ] Import cards from CSV or Anki
- [ ] More courses (pandas, Git, machine learning basics)
- [ ] Python exercises graded by running your code in a sandbox
