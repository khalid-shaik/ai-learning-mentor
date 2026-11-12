"""Optional local AI (Ollama) for the mentor: re-explanations, teach-back feedback, answers and flashcards from notes."""
import json
import re

import ollama

SYSTEM = ("You are a patient, accurate tutor. Use ONLY the provided material for facts; if it does not contain the answer, say so. "
          "Reply with a single valid JSON object only.")


def parse_json(raw: str) -> dict:
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.S)
        if not m:
            raise ValueError("Model did not return JSON.")
        return json.loads(m.group(0))


def list_models(host: str | None = None) -> list[str]:
    try:
        client = ollama.Client(host=host) if host else ollama.Client()
        resp = client.list()
        models = resp["models"] if isinstance(resp, dict) else resp.models
        return sorted((m["model"] if isinstance(m, dict) else m.model) for m in models)
    except Exception:
        return []


def _chat(prompt, model, host, temperature) -> dict:
    client = ollama.Client(host=host) if host else ollama.Client()
    resp = client.chat(model=model, messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
                       format="json", options={"temperature": temperature})
    content = resp["message"]["content"] if isinstance(resp, dict) else resp.message.content
    return parse_json(content)


def _list(v):
    return [str(x).strip() for x in v if str(x).strip()] if isinstance(v, list) else []


def normalize_explain(d: dict) -> dict:
    return {"explanation": str(d.get("explanation", "")).strip(), "analogy": str(d.get("analogy", "")).strip(), "check_question": str(d.get("check_question", "")).strip()}


def normalize_critique(d: dict) -> dict:
    return {"feedback": str(d.get("feedback", "")).strip(), "correct": _list(d.get("correct")), "misconceptions": _list(d.get("misconceptions")), "improve": _list(d.get("improve"))}


def normalize_answer(d: dict, n: int) -> dict:
    cited = []
    for c in d.get("cited", []) if isinstance(d.get("cited"), list) else []:
        try:
            c = int(c)
        except (TypeError, ValueError):
            continue
        if 1 <= c <= n and c not in cited:
            cited.append(c)
    return {"answer": str(d.get("answer", "")).strip(), "cited": cited}


def normalize_cards(d: dict) -> list[dict]:
    out, seen = [], set()
    for c in d.get("cards", []) if isinstance(d.get("cards"), list) else []:
        if isinstance(c, dict) and str(c.get("front", "")).strip() and str(c.get("back", "")).strip():
            f = str(c["front"]).strip()
            if f.lower() not in seen:
                seen.add(f.lower())
                out.append({"front": f, "back": str(c["back"]).strip(), "kind": "ai", "sentence": ""})
    return out[:15]


def explain(lesson_title, material, style, model="llama3.2", host=None, temperature=0.5) -> dict:
    prompt = (f"Re-explain this lesson ({lesson_title}) in the style: {style}. Keep it under 150 words and stay faithful to the material.\n\nMATERIAL:\n{material[:4000]}\n\n"
              'Return JSON: {"explanation": "...", "analogy": "one everyday analogy", "check_question": "one question to test understanding"}')
    return normalize_explain(_chat(prompt, model, host, temperature))


def critique(lesson_title, points, student_text, model="llama3.2", host=None, temperature=0.2) -> dict:
    prompt = (f"A student explained '{lesson_title}' in their own words. Compare with the key ideas and give kind, specific feedback.\nKEY IDEAS:\n- " + "\n- ".join(points) +
              f"\n\nSTUDENT EXPLANATION:\n{student_text[:3000]}\n\n"
              'Return JSON: {"feedback": "2-3 sentences", "correct": ["ideas they got right"], "misconceptions": ["anything wrong"], "improve": ["specific next steps"]}')
    return normalize_critique(_chat(prompt, model, host, temperature))


def answer(question: str, passages: list[str], model="llama3.2", host=None, temperature=0.1) -> dict:
    listing = "\n".join(f"[{i}] {p}" for i, p in enumerate(passages, 1))
    prompt = (f"Answer the question using ONLY these passages. If they do not contain the answer say so. Max 5 sentences. Cite passage numbers.\n\nPASSAGES:\n{listing}\n\nQUESTION: {question}\n"
              'Return JSON: {"answer": "...", "cited": [1]}')
    return normalize_answer(_chat(prompt, model, host, temperature), len(passages))


def cards_from_notes(text: str, model="llama3.2", host=None, temperature=0.2) -> list[dict]:
    prompt = (f"Create 6-10 high-quality flashcards from these notes. Each card tests one idea, with a clear question and a short answer. Use only the notes.\n\nNOTES:\n{text[:5000]}\n\n"
              'Return JSON: {"cards": [{"front": "question", "back": "answer"}]}')
    return normalize_cards(_chat(prompt, model, host, temperature))
