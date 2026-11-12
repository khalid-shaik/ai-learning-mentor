"""Small BM25 search over lessons and your notes (for 'Ask the mentor')."""
import math
import re
from collections import Counter

from .courses import LESSONS

STOP = set("a an the and or but if to of in on at for with from by as is are was were be it its this that i you we they what how why when do does can should about".split())


def tokens(text: str) -> list[str]:
    return [re.sub(r"(ing|ed|es|s)$", "", w) if len(w) > 4 else w for w in re.findall(r"[a-z0-9][a-z0-9+#/_-]*", text.lower()) if w not in STOP]


def lesson_docs() -> list[dict]:
    docs = []
    for l in LESSONS.values():
        for i, para in enumerate(p for p in re.split(r"\n\s*\n", l["body"]) if p.strip()):
            docs.append({"id": f"{l['id']}#{i}", "source": "lesson", "ref": l["id"], "title": l["title"], "text": para.strip()})
        docs.append({"id": f"{l['id']}#kp", "source": "lesson", "ref": l["id"], "title": l["title"], "text": " ".join(p for p, _ in l["points"])})
    return docs


def note_docs(notes: list[dict]) -> list[dict]:
    docs = []
    for n in notes:
        for i, para in enumerate(p for p in re.split(r"\n\s*\n|\n", n["text"]) if len(p.split()) >= 5):
            docs.append({"id": f"note{n['id']}#{i}", "source": "note", "ref": str(n["id"]), "title": n["title"], "text": para.strip()})
    return docs


def search(query: str, docs: list[dict], k: int = 4) -> list[dict]:
    q = tokens(query)
    if not q or not docs:
        return []
    toks = [Counter(tokens(d["text"] + " " + d["title"])) for d in docs]
    avg = sum(sum(t.values()) for t in toks) / len(toks) or 1
    df = Counter(w for t in toks for w in t)
    n = len(docs)
    scored = []
    for d, t in zip(docs, toks):
        length = sum(t.values())
        s = sum(math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5)) * (t[w] * 2.5) / (t[w] + 1.5 * (0.25 + 0.75 * length / avg)) for w in set(q) if t[w])
        if s > 0:
            scored.append((s, d))
    return [{**d, "score": round(s, 3)} for s, d in sorted(scored, key=lambda x: -x[0])[:k]]
