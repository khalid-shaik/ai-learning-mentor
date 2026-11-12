"""Mastery maths."""


def lesson_mastery(best_quiz: float | None, learned_cards: int, total_cards: int, ex_passed: int, ex_total: int) -> int:
    """0-100. Quiz 50%, retained flashcards 30%, SQL exercises 20% (weights are redistributed when a part does not exist)."""
    parts = [(0.5, best_quiz or 0.0)]
    parts.append((0.3, learned_cards / total_cards if total_cards else 0.0))
    if ex_total:
        parts.append((0.2, ex_passed / ex_total))
    w = sum(p[0] for p in parts)
    return round(100 * sum(wt * v for wt, v in parts) / w)
