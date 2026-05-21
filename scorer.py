# scorer.py

import re

WEIGHTS = {
    "coverage":  0.20,
    "relevance": 0.30,
    "structure": 0.20,
    "edge_cases": 0.15,
    "clarity":   0.15,
}


def score(parsed: dict, feature: str, requested_count: int) -> dict:

    tc_list = parsed.get("test_cases", [])

    n = len(tc_list)

    if n == 0:
        return {
            "coverage": 0,
            "relevance": 0,
            "structure": 0,
            "edge_cases": 0,
            "clarity": 0,
            "overall": 0,
            "count": 0,
        }

    # ── Duplicate title penalty ───────────────────────────────

    titles = [
        tc.get("title", "").strip().lower()
        for tc in tc_list
    ]

    unique_titles = len(set(titles))

    dup_penalty = max(
        0,
        (n - unique_titles) * 10
    )

    # ── Coverage ──────────────────────────────────────────────

    coverage = min(
        100,
        round((n / requested_count) * 100)
    )

    # ── Relevance ─────────────────────────────────────────────

    feature_words = [
        w for w in re.split(r'\W+', feature.lower())
        if len(w) > 3
    ]

    rel_scores = []

    for tc in tc_list:

        blob = " ".join([
            tc.get("title", ""),
            " ".join(tc.get("steps", [])),
            tc.get("expected_result", ""),
            tc.get("preconditions", ""),
        ]).lower()

        hits = sum(
            1 for w in feature_words
            if w in blob
        )

        threshold = max(
            1,
            len(feature_words) * 0.25
        )

        rel_scores.append(
            min(1.0, hits / threshold)
        )

    relevance = round(
        (sum(rel_scores) / n) * 100
    )

    # ── Structure ─────────────────────────────────────────────

    struct_scores = []

    for tc in tc_list:

        s = 0

        if tc.get("id"):
            s += 5

        if tc.get("title") and len(tc["title"]) >= 8:
            s += 15

        if tc.get("type") in (
            "positive",
            "negative",
            "edge"
        ):
            s += 10

        if tc.get("priority") in (
            "high",
            "medium",
            "low"
        ):
            s += 10

        if tc.get("preconditions") and len(tc["preconditions"]) > 5:
            s += 15

        steps = tc.get("steps", [])

        if isinstance(steps, list) and len(steps) >= 2:
            s += 25

        if tc.get("expected_result") and len(tc["expected_result"]) > 10:
            s += 15

        if tc.get("category"):
            s += 5

        struct_scores.append(s)

    structure = round(
        sum(struct_scores) / n
    )

    # ── Edge cases ────────────────────────────────────────────

    edge_pattern = re.compile(
        r'edge|boundary|invalid|null|empty|max|min|overflow|exceed|zero|none|missing|corrupt',
        re.IGNORECASE
    )

    neg_pattern = re.compile(
        r'fail|error|wrong|unauthori|deny|reject|block|timeout|exceed|expired|missing',
        re.IGNORECASE
    )

    edge_count = sum(
        1 for tc in tc_list
        if tc.get("type") == "edge"
        or edge_pattern.search(tc.get("title", ""))
    )

    neg_count = sum(
        1 for tc in tc_list
        if tc.get("type") == "negative"
        or neg_pattern.search(tc.get("title", ""))
    )

    raw_ratio = (
        edge_count + neg_count * 0.7
    ) / n

    edge_cases = min(
        100,
        round(raw_ratio * 180)
    )

    # ── Diversity penalty ─────────────────────────────────────

    types = [
        tc.get("type")
        for tc in tc_list
    ]

    type_diversity = len(set(types))

    diversity_penalty = max(
        0,
        (3 - type_diversity) * 15
    )

    # ── Clarity ───────────────────────────────────────────────

    generic_phrases = [
        "verify",
        "check",
        "ensure",
        "validate"
    ]

    clarity_scores = []

    for tc in tc_list:

        c = 50

        title_len = len(
            tc.get("title", "")
        )

        if 10 <= title_len <= 90:
            c += 20

        steps = tc.get("steps", [])

        step_blob = " ".join(steps).lower()

        generic_hits = sum(
            1 for g in generic_phrases
            if g in step_blob
        )

        c -= generic_hits * 3

        if (
            isinstance(steps, list)
            and all(
                isinstance(s, str)
                and len(s) > 8
                for s in steps
            )
        ):
            c += 20

        er = tc.get(
            "expected_result",
            ""
        )

        if er and len(er) > 15:
            c += 10

        clarity_scores.append(c)

    clarity = round(
        sum(clarity_scores) / n
    )

    # ── Overall ───────────────────────────────────────────────

    overall = round(

        coverage   * WEIGHTS["coverage"]  +
        relevance  * WEIGHTS["relevance"] +
        structure  * WEIGHTS["structure"] +
        edge_cases * WEIGHTS["edge_cases"] +
        clarity    * WEIGHTS["clarity"]

        - dup_penalty
        - diversity_penalty
    )

    overall = max(
        0,
        min(100, overall)
    )

    # ── Final result ──────────────────────────────────────────

    return {

        "coverage": coverage,

        "relevance": relevance,

        "structure": structure,

        "edge_cases": edge_cases,

        "clarity": clarity,

        "overall": overall,

        "count": n,

        "positive_count": sum(
            1 for tc in tc_list
            if tc.get("type") == "positive"
        ),

        "negative_count": sum(
            1 for tc in tc_list
            if tc.get("type") == "negative"
        ),

        "edge_count": sum(
            1 for tc in tc_list
            if tc.get("type") == "edge"
        ),
    }