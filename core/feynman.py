"""Teach-it-back checker: how well does your own explanation cover the key ideas?"""
import re


def _stem(w: str) -> str:
    return re.sub(r"(ing|ed|es|s)$", "", w) if len(w) > 4 else w


def covers(text: str, keywords: list[str]) -> int:
    t = text.lower()
    toks = {_stem(w) for w in re.findall(r"[a-z0-9/+#.-]+", t)}
    n = 0
    for k in keywords:
        k = k.lower()
        if " " in k or not k.isalpha():
            n += k in t
        else:
            n += _stem(k) in toks
    return n


def check_explanation(text: str, points: list[tuple[str, list[str]]]) -> dict:
    words = len(text.split())
    low = text.lower()
    covered, missing = [], []
    for point, kws in points:
        need = 1 if len(kws) <= 2 else 2
        (covered if covers(text, kws) >= need else missing).append(point)
    coverage = len(covered) / len(points) if points else 0.0
    has_example = bool(re.search(r"\b(for example|for instance|such as|e\.g\.|suppose|imagine)\b", low))
    has_analogy = bool(re.search(r"\b(like a|like an|as if|think of|similar to|imagine|analogy|(is|are|works|acts?) like)\b", low))
    len_ok = 40 <= words <= 250
    score = round(70 * coverage + (10 if len_ok else 0) + (10 if has_example else 0) + (10 if has_analogy else 0))
    tips = []
    if words < 40:
        tips.append("Too short: explain it in at least 40 words as if teaching a friend.")
    elif words > 250:
        tips.append("Too long: tighten it to the essentials (under about 250 words).")
    if not has_example:
        tips.append("Add a concrete example (start with 'for example').")
    if not has_analogy:
        tips.append("Try an analogy ('it is like ...') to show real understanding.")
    if missing:
        tips.append(f"You did not cover {len(missing)} key idea(s). Review them below and try again.")
    return {"score": min(100, score), "covered": covered, "missing": missing, "tips": tips, "words": words, "example": has_example, "analogy": has_analogy}
