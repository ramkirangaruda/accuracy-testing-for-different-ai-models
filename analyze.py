# analyze.py
# Read saved JSON results and print a formatted comparison table.
#
# Usage (after saving results with Invoke-RestMethod or curl):
#   venv\Scripts\python analyze.py skills_results.json
#   venv\Scripts\python analyze.py jd_results.json

import json
import sys
import re
from pathlib import Path

# ── Skill-output quality checks ───────────────────────────────────────────

VAGUE_SKILLS = {
    "big data technologies", "data technologies", "machine learning frameworks",
    "cloud technologies", "programming skills",
}

BANNED_JD_PHRASES = [
    "dynamic team", "fast-paced", "passionate individuals",
    "cutting-edge", "drive growth", "foster innovation",
    "actionable insights", "complex data sets", "synergy",
    "the ideal candidate", "we are seeking", "self-starter",
    "competitive salary", "comprehensive benefits", "collaborative work environment",
]

REQUIRED_HEADERS = [
    "about the team", "what you'll do", "what you bring",
    "nice to have", "details",
]


def audit_skills(response_text: str) -> list[str]:
    """Return a list of rule violations found in a skill response."""
    issues = []
    try:
        data = json.loads(response_text)
    except Exception:
        return ["[parse error — not valid JSON]"]

    req = data.get("required_skills", [])
    opt = data.get("optional_skills", [])

    if len(req) > 4:
        issues.append(f"Too many required skills ({len(req)}, max 4)")
    if len(opt) > 4:
        issues.append(f"Too many optional skills ({len(opt)}, max 4)")

    all_skills = [s.lower() for s in req + opt]
    for s in all_skills:
        if s in VAGUE_SKILLS:
            issues.append(f"Vague skill kept: '{s}'")

    if not data.get("removed_skills"):
        issues.append("No skills removed / no removal reasoning provided")

    salary_flag = data.get("salary_flag", "").lower()
    if salary_flag not in ("ok",) and not salary_flag:
        issues.append("salary_flag missing")

    return issues


def audit_jd(response_text: str) -> list[str]:
    """Return a list of rule violations found in a JD response."""
    issues = []
    lower = response_text.lower()

    for phrase in BANNED_JD_PHRASES:
        if phrase in lower:
            issues.append(f"Banned phrase used: '{phrase}'")

    missing_headers = [h for h in REQUIRED_HEADERS if h not in lower]
    if missing_headers:
        issues.append(f"Missing headers: {missing_headers}")

    # Second-person check (rough: should have "you will" or "you'll")
    if "you will" not in lower and "you'll" not in lower:
        issues.append("Not written in second person (no 'You will'/'You'll')")

    word_count = len(response_text.split())
    if word_count < 250:
        issues.append(f"Too short ({word_count} words, min 250)")
    elif word_count > 450:
        issues.append(f"Too long ({word_count} words, max 450)")

    return issues


# ── Rendering ─────────────────────────────────────────────────────────────

BAR = "━" * 78

def fmt_cost(v):
    if v is None:
        return "n/a"
    if v == 0.0:
        return "$0.000000"
    return f"${v:.6f}"


def render_skills(results: list[dict]) -> None:
    print(f"\n{BAR}")
    print(f"  SKILLS COMPARISON — {len(results)} models")
    print(BAR)
    print(f"  {'MODEL':<42} {'LAT':>6} {'IN':>6} {'OUT':>6} {'COST':>10}  ISSUES")
    print(BAR)

    for r in sorted(results, key=lambda x: x.get("latency_ms") or 99999):
        model = r["model"][:42]
        lat = f"{r.get('latency_ms') or 0}ms"
        inp = str(r.get("input_tokens") or "-")
        out = str(r.get("output_tokens") or "-")
        cost = fmt_cost(r.get("cost_estimate_usd"))

        if r.get("error"):
            print(f"  {model:<42} {'ERR':>6} {'-':>6} {'-':>6} {'n/a':>10}  ERROR: {r['error'][:60]}")
            continue

        issues = audit_skills(r.get("response", ""))
        flag = "OK" if not issues else f"{len(issues)} issue(s)"
        print(f"  {model:<42} {lat:>6} {inp:>6} {out:>6} {cost:>10}  {flag}")

        for issue in issues:
            print(f"    {'':42}    ↳ {issue}")

    print(BAR)
    print("\n  SKILL RESPONSES\n" + BAR)

    for r in results:
        print(f"\n  [{r['model']}]")
        if r.get("error"):
            print(f"  ERROR: {r['error']}")
            continue
        try:
            parsed = json.loads(r.get("response", "{}"))
            print(f"  Required : {parsed.get('required_skills', [])}")
            print(f"  Optional : {parsed.get('optional_skills', [])}")
            removed = parsed.get("removed_skills", {})
            if removed:
                for skill, reason in removed.items():
                    print(f"  Removed  : {skill} — {reason}")
            print(f"  Salary   : {parsed.get('salary_flag', '-')}")
        except Exception:
            print(f"  (raw) {(r.get('response') or '')[:300]}")


def render_jd(results: list[dict]) -> None:
    print(f"\n{BAR}")
    print(f"  JD COMPARISON — {len(results)} models")
    print(BAR)
    print(f"  {'MODEL':<42} {'LAT':>6} {'IN':>6} {'OUT':>6} {'COST':>10}  WORDS  ISSUES")
    print(BAR)

    for r in sorted(results, key=lambda x: x.get("latency_ms") or 99999):
        model = r["model"][:42]
        lat = f"{r.get('latency_ms') or 0}ms"
        inp = str(r.get("input_tokens") or "-")
        out = str(r.get("output_tokens") or "-")
        cost = fmt_cost(r.get("cost_estimate_usd"))

        if r.get("error"):
            print(f"  {model:<42} {'ERR':>6} {'-':>6} {'-':>6} {'n/a':>10}     -   ERROR: {r['error'][:50]}")
            continue

        text = r.get("response", "")
        issues = audit_jd(text)
        words = len(text.split())
        flag = "OK" if not issues else f"{len(issues)} issue(s)"
        print(f"  {model:<42} {lat:>6} {inp:>6} {out:>6} {cost:>10} {words:>5}   {flag}")

        for issue in issues:
            print(f"    {'':42}    ↳ {issue}")

    print(BAR)
    print("\n  JD RESPONSES (first 600 chars each)\n" + BAR)

    for r in results:
        print(f"\n  [{r['model']}]")
        if r.get("error"):
            print(f"  ERROR: {r['error']}")
        else:
            snippet = (r.get("response") or "")[:600]
            # indent for readability
            for line in snippet.splitlines():
                print(f"  {line}")
            if len(r.get("response", "")) > 600:
                print("  ...")


def render_summary(results: list[dict], mode: str) -> None:
    print(f"\n{BAR}")
    print("  SUMMARY — pick your model")
    print(BAR)

    ok_results = [r for r in results if not r.get("error")]
    err_results = [r for r in results if r.get("error")]

    if mode == "skills":
        scored = []
        for r in ok_results:
            issues = audit_skills(r.get("response", ""))
            scored.append((r, len(issues)))
        scored.sort(key=lambda x: (x[1], x[0].get("latency_ms") or 99999))
    else:
        scored = []
        for r in ok_results:
            issues = audit_jd(r.get("response", ""))
            scored.append((r, len(issues)))
        scored.sort(key=lambda x: (x[1], x[0].get("latency_ms") or 99999))

    print(f"\n  Best (fewest rule violations, then fastest):\n")
    for rank, (r, issue_count) in enumerate(scored, 1):
        badge = " ← WINNER" if rank == 1 else ""
        print(
            f"  #{rank}  {r['model']:<42}  "
            f"{issue_count} violation(s)  "
            f"{r.get('latency_ms')}ms  "
            f"{fmt_cost(r.get('cost_estimate_usd'))}"
            f"{badge}"
        )

    if err_results:
        print(f"\n  Failed ({len(err_results)} model(s)):")
        for r in err_results:
            print(f"    {r['model']} — {r.get('error', '')[:80]}")

    print(BAR)


# ── Entry point ───────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: python analyze.py <results_file.json>")
        sys.exit(1)

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"File not found: {path}")
        sys.exit(1)

    raw = json.loads(path.read_text(encoding="utf-8"))

    # Handle both direct list and wrapped { results: [...] }
    if isinstance(raw, list):
        results = raw
    elif "results" in raw:
        results = raw["results"]
        if raw.get("input_used"):
            print(f"\n  Input: {json.dumps(raw['input_used'], ensure_ascii=False)[:120]}…")
    else:
        print("Unexpected JSON shape — expected a list or {results: [...]}")
        sys.exit(1)

    # Detect mode from data shape
    first_ok = next((r for r in results if r.get("response")), None)
    if first_ok:
        try:
            json.loads(first_ok["response"])
            mode = "skills"
        except Exception:
            mode = "jd"
    else:
        mode = "jd"

    print(f"\n  Mode detected: {mode.upper()}")

    if mode == "skills":
        render_skills(results)
    else:
        render_jd(results)

    render_summary(results, mode)


if __name__ == "__main__":
    main()
