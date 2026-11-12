"""Turn your own notes into study material, offline: key terms, summary, flashcards and multiple-choice questions."""
import random
import re
from collections import Counter

STOP = set("""a an the and or but if then so to of in on at for with from by as is are was were be been it its this that these those i you he she we they me my your our
their not no do does did have has had will would can could should may might just also very more most some any all about into over under again there here what which who
whom when where why how than too out up down off only own same such each other both between during after before while because since until using used use uses many much
often usually every like called known""".split())
DEF_RE = re.compile(r"^(?P<term>[A-Z][\w/\- ]{1,40}?)\s+(?:is|are|refers to|means|is defined as|describes|represents)\s+(?P<defn>.{12,})$")
COLON_RE = re.compile(r"^(?P<term>[A-Z][\w/\- ]{1,40}):\s+(?P<defn>.{12,})$")


def sentences(text: str) -> list[str]:
    out = []
    for line in (text or "").replace("\r", "").split("\n"):
        line = re.sub(r"^\s*(?:[-*•]|\d+[.)]|#+)\s*", "", line.strip())
        if not line:
            continue
        for s in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])", line):
            if s.strip():
                out.append(s.strip())
    return out


def _words(s: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z'-]*", s)


def key_terms(text: str, top: int = 12) -> list[str]:
    emphasised = [m.strip() for m in re.findall(r"\*\*([^*]{2,40})\*\*", text or "")]
    scores: Counter = Counter()
    for t in emphasised:
        scores[t.lower()] += 6
    toks = [w.lower() for w in _words(text or "")]
    for i, w in enumerate(toks):
        if w not in STOP and len(w) > 3:
            scores[w] += 1
        if i + 1 < len(toks) and w not in STOP and toks[i + 1] not in STOP and len(w) > 2 and len(toks[i + 1]) > 2:
            scores[f"{w} {toks[i + 1]}"] += 1.6
    ranked = [t for t, s in scores.most_common() if s >= 2.5 or t in {e.lower() for e in emphasised}]
    chosen = []
    for t in ranked:  # drop a unigram that is part of a better bigram
        if any(t != c and t in c.split() for c in chosen):
            continue
        chosen.append(t)
        if len(chosen) >= top:
            break
    return chosen


def definition_cards(text: str) -> list[dict]:
    cards, seen = [], set()
    for s in sentences(text):
        m = DEF_RE.match(s) or COLON_RE.match(s)
        if m and len(m["term"].split()) <= 4:
            term, defn = m["term"].strip(), m["defn"].strip().rstrip(".")
            if term.lower() not in seen and term.lower().split()[0] not in STOP:
                seen.add(term.lower())
                cards.append({"front": f"What is {term}?", "back": defn[:1].upper() + defn[1:], "kind": "definition", "sentence": s})
    return cards


def cloze_cards(text: str, terms: list[str], max_cards: int = 10, skip: set[str] | None = None) -> list[dict]:
    cards, used = [], set(skip or [])
    for s in sentences(text):
        n = len(s.split())
        if s in used or not 8 <= n <= 35:
            continue
        for t in terms:
            m = re.search(rf"(?<![A-Za-z]){re.escape(t)}(?![A-Za-z])", s, re.I)
            if m and m.start() > 0:
                cards.append({"front": (s[:m.start()] + "_____" + s[m.end():]), "back": m.group(0), "kind": "cloze", "sentence": s})
                used.add(s)
                break
        if len(cards) >= max_cards:
            break
    return cards


def mcq_from_cloze(cards: list[dict], terms: list[str], n: int = 5, seed: int = 0) -> list[dict]:
    rng = random.Random(seed)
    out = []
    for c in cards:
        ans = c["back"]
        pool = [t for t in terms if t.lower() != ans.lower()]
        same = [t for t in pool if (" " in t) == (" " in ans)] or pool
        if len(pool) < 3:
            continue
        distract = rng.sample(same, 3) if len(same) >= 3 else (same + [t for t in pool if t not in same])[:3]
        options = distract + [ans]
        rng.shuffle(options)
        out.append({"q": "Fill in the blank: " + c["front"], "options": options, "answer": options.index(ans), "why": c["sentence"], "id": f"note-{len(out)}"})
        if len(out) >= n:
            break
    return out


def summarize(text: str, n: int = 3) -> list[str]:
    sents = [s for s in sentences(text) if len(s.split()) >= 6]
    if len(sents) <= n:
        return sents
    freq = Counter(w.lower() for s in sents for w in _words(s) if w.lower() not in STOP and len(w) > 3)
    top = max(freq.values()) if freq else 1
    scored = []
    for i, s in enumerate(sents):
        ws = [w.lower() for w in _words(s) if w.lower() not in STOP and len(w) > 3]
        scored.append((sum(freq[w] / top for w in ws) / (max(1, len(ws)) ** 0.6) + (0.3 if i == 0 else 0), i, s))
    return [s for _, _, s in sorted(sorted(scored, reverse=True)[:n], key=lambda x: x[1])]


def study_pack(text: str) -> dict:
    defs = definition_cards(text)
    terms = list(dict.fromkeys([d["front"][8:-1].lower() for d in defs] + key_terms(text)))[:14]
    cloze = cloze_cards(text, terms, skip={d["sentence"] for d in defs})
    return {"terms": terms, "summary": summarize(text), "definitions": defs, "cloze": cloze, "mcqs": mcq_from_cloze(cloze, terms)}
