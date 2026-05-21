#!/usr/bin/env python3

import argparse
import json
import os
import re
import time

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from models import AVAILABLE_MODELS
from prompt_template import SYSTEM_PROMPT, build_user_prompt
from scorer import score
from scenarios import SCENARIOS

# ── Setup ────────────────────────────────────────────────────────────────

load_dotenv()

client = OpenAI(
    api_key=os.getenv("API_KEY"),
    base_url="https://api.groq.com/openai/v1",
)

RESULTS_DIR = Path("results")
RESULTS_DIR.mkdir(exist_ok=True)

# ── Helpers ──────────────────────────────────────────────────────────────

def extract_json(text: str) -> dict:

    clean = re.sub(r"```(?:json)?\s*", "", text).strip()

    try:
        return json.loads(clean)

    except json.JSONDecodeError:

        match = re.search(r"\{[\s\S]+\}", clean)

        if match:
            try:
                return json.loads(match.group())

            except json.JSONDecodeError:
                pass

    return {
        "test_cases": [],
        "_parse_error": True
    }


def call_model(
    model_id: str,
    user_prompt: str,
    max_tokens: int = 2000
) -> dict:

    t0 = time.time()

    try:

        resp = client.chat.completions.create(

            model=model_id,

            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": user_prompt
                },
            ],

            response_format={
                "type": "json_object"
            },

            max_tokens=max_tokens,
            temperature=0.3,
        )

        raw_text = resp.choices[0].message.content or ""

        latency_ms = round(
            (time.time() - t0) * 1000
        )

        return {
            "ok": True,
            "raw_text": raw_text,
            "latency_ms": latency_ms,
            "model": model_id,
        }

    except Exception as exc:

        latency_ms = round(
            (time.time() - t0) * 1000
        )

        return {
            "ok": False,
            "error": str(exc),
            "latency_ms": latency_ms,
            "model": model_id,
        }
def run_model(
    model_id: str,
    user_prompt: str,
    feature: str,
    requested_count: int
) -> dict:

    print(f"  ⏳  {model_id} ...", flush=True)

    result = call_model(model_id, user_prompt)

    if not result["ok"]:

        print(
            f"  ✗   {model_id} — ERROR: "
            f"{result['error'][:80]}"
        )

        return {
            "model": model_id,
            "ok": False,
            "error": result["error"],
            "latency_ms": result["latency_ms"],
            "parsed": {},
            "scores": {
                k: 0 for k in [
                    "coverage",
                    "relevance",
                    "structure",
                    "edge_cases",
                    "clarity",
                    "overall",
                    "count"
                ]
            },
        }

    parsed = extract_json(result["raw_text"])

    scores = score(
        parsed,
        feature,
        requested_count
    )

    ok_msg = (
        "✓"
        if not parsed.get("_parse_error")
        else "⚠ JSON parse error"
    )

    print(
        f"  {ok_msg}  {model_id} — "
        f"overall: {scores['overall']}%  "
        f"({result['latency_ms']}ms)"
    )

    return {
        "model": model_id,
        "ok": True,
        "latency_ms": result["latency_ms"],
        "raw_text": result["raw_text"],
        "parsed": parsed,
        "scores": scores,
    }


# ── Main ─────────────────────────────────────────────────────────────────

def main():

    parser = argparse.ArgumentParser(
        description="TestServ AI Model Comparator"
    )

    parser.add_argument(
        "--feature",

        default=(
            "User login with email and password. "
            "The system validates credentials, "
            "locks the account after 5 failed attempts, "
            "supports remember-me for 30 days, "
            "and sends a verification email "
            "on first login from a new device."
        ),

        help="Feature description"
    )

    parser.add_argument(
        "--focus",

        default="functional",

        choices=[
            "functional",
            "api",
            "security",
            "boundary",
            "regression",
            "performance"
        ],

        help="Type of tests"
    )

    parser.add_argument(
        "--count",
        default=8,
        type=int
    )

    parser.add_argument(
        "--models",
        nargs="*",
        default=None
    )

    parser.add_argument(
    "--workers",
    default=1,
    type=int
)

    args = parser.parse_args()

    models_to_run = (
        args.models
        if args.models
        else AVAILABLE_MODELS
    )

    all_results = []

    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  TestServ AI Model Comparator — iFocus Systec")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    print(f"  Focus   : {args.focus}")
    print(f"  Count   : {args.count} test cases per model")
    print(f"  Models  : {len(models_to_run)}")
    print(f"  Workers : {args.workers}")
    print(f"  Scenarios : {len(SCENARIOS)}")

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

    for scenario in SCENARIOS:

        print(f"\n=== Scenario: {scenario['name']} ===\n")

        user_prompt = build_user_prompt(
            scenario["feature"],
            args.count,
            args.focus
        )

        with ThreadPoolExecutor(
            max_workers=args.workers
        ) as pool:

            futures = {

                pool.submit(
                    run_model,
                    m,
                    user_prompt,
                    scenario["feature"],
                    args.count
                ): m

                for m in models_to_run
            }

            for fut in as_completed(futures):

                result = fut.result()

                result["scenario"] = scenario["name"]

                all_results.append(result)

    # Sort best → worst

    all_results.sort(
        key=lambda r: r["scores"]["overall"],
        reverse=True
    )

    all_results.sort(
        key=lambda r: r["scores"]["overall"],
        reverse=True
    )

    # ── Save results ────────────────────────────────────────────────

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    out_file = RESULTS_DIR / f"run_{timestamp}.json"

    payload = {

        "meta": {

            "timestamp":
                datetime.now().isoformat(),

            "feature":
                args.feature,

            "focus":
                args.focus,

            "requested_count":
                args.count,

            "models_run":
                len(models_to_run),

            "models_ok":
                sum(
                    1 for r in all_results
                    if r["ok"]
                ),
        },

        "results":
            all_results,
    }

    # Save timestamped run

    out_file.write_text(

        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False
        ),

        encoding="utf-8"
    )

    # Save latest.json

    (RESULTS_DIR / "latest.json").write_text(

        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False
        ),

        encoding="utf-8"
    )

    # ── Summary ─────────────────────────────────────────────────────

    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    print(
        f"  {'RANK':<5} "
        f"{'MODEL':<40} "
        f"{'OVERALL':>8} "
        f"{'LATENCY':>9}"
    )

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    for i, r in enumerate(all_results, 1):

        status = (
            f"{r['scores']['overall']}%"
            if r["ok"]
            else "FAILED"
        )

        lat = f"{r['latency_ms']}ms"

        name = r["model"][:38]

        print(
            f"  {i:<5} "
            f"{name:<40} "
            f"{status:>8} "
            f"{lat:>9}"
        )

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    print(f"\n  Results saved → {out_file}")
    print("  Dashboard     → http://localhost:8000/dashboard\n")


if __name__ == "__main__":
    main()