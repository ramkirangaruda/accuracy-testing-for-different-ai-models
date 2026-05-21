#!/usr/bin/env python3

import argparse
import json
import os
import re
import time
import difflib

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from models import AVAILABLE_MODELS
from prompt_template import SYSTEM_PROMPT, build_user_prompt
from scorer import score
from scenarios import SCENARIOS

REPEAT_COUNT = 5

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


def similarity(a: str, b: str) -> float:

    return round(
        difflib.SequenceMatcher(
            None,
            a,
            b
        ).ratio() * 100,
        2
    )


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
    requested_count: int,
    scenario: dict,
    run_number: int
) -> dict:

    print(
        f"  ⏳ {model_id} "
        f"| Scenario: {scenario['name']} "
        f"| Run {run_number}"
    )

    result = call_model(model_id, user_prompt)

    if not result["ok"]:

        print(
            f"  ✗ {model_id} ERROR: "
            f"{result['error'][:80]}"
        )

        return {
            "scenario_name": scenario["name"],
            "scenario_type": scenario["type"],
            "scenario_domain": scenario["domain"],
            "difficulty": scenario["difficulty"],
            "run_number": run_number,
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
                    "count",
                    "consistency"
                ]
            },
        }

    parsed = extract_json(result["raw_text"])

    scores = score(
        parsed,
        feature,
        requested_count
    )

    print(
        f"  ✓ {model_id} "
        f"| overall: {scores['overall']}% "
        f"| latency: {result['latency_ms']}ms"
    )

    return {
        "scenario_name": scenario["name"],
        "scenario_type": scenario["type"],
        "scenario_domain": scenario["domain"],
        "difficulty": scenario["difficulty"],
        "run_number": run_number,
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

    print(f"  Focus      : {args.focus}")
    print(f"  Count      : {args.count}")
    print(f"  Models     : {len(models_to_run)}")
    print(f"  Workers    : {args.workers}")
    print(f"  Scenarios  : {len(SCENARIOS)}")
    print(f"  Repeats    : {REPEAT_COUNT}")

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

            futures = []

            for model_id in models_to_run:

                for run_number in range(
                    1,
                    REPEAT_COUNT + 1
                ):

                    futures.append(

                        pool.submit(
                            run_model,
                            model_id,
                            user_prompt,
                            scenario["feature"],
                            args.count,
                            scenario,
                            run_number
                        )
                    )

            for fut in as_completed(futures):

                result = fut.result()

                all_results.append(result)

    # ── Consistency Analysis ─────────────────────────────────────────────

    grouped = {}

    for r in all_results:

        if not r["ok"]:
            continue

        key = (
            r["scenario_name"],
            r["model"]
        )

        grouped.setdefault(key, []).append(r)

    for key, runs in grouped.items():

        similarities = []

        for i in range(len(runs)):

            for j in range(i + 1, len(runs)):

                sim = similarity(
                    runs[i]["raw_text"],
                    runs[j]["raw_text"]
                )

                similarities.append(sim)

        consistency = (
            round(sum(similarities) / len(similarities), 2)
            if similarities else 100
        )

        for r in runs:
            r["scores"]["consistency"] = consistency

    # ── Sort Best → Worst ────────────────────────────────────────────────

    all_results.sort(
        key=lambda r: (
            r["scores"]["overall"],
            r["scores"].get("consistency", 0)
        ),
        reverse=True
    )

    # ── Save Results ─────────────────────────────────────────────────────

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    out_file = RESULTS_DIR / f"run_{timestamp}.json"

    payload = {

        "meta": {

            "timestamp":
                datetime.now().isoformat(),

            "focus":
                args.focus,

            "requested_count":
                args.count,

            "models_run":
                len(models_to_run),

            "scenarios":
                len(SCENARIOS),

            "repeat_count":
                REPEAT_COUNT,
        },

        "results":
            all_results,
    }

    out_file.write_text(

        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False
        ),

        encoding="utf-8"
    )

    (RESULTS_DIR / "latest.json").write_text(

        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False
        ),

        encoding="utf-8"
    )

    # ── Summary ──────────────────────────────────────────────────────────

    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    print(
        f"  {'MODEL':<35} "
        f"{'OVERALL':>10} "
        f"{'CONSISTENCY':>14} "
        f"{'LATENCY':>10}"
    )

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    for r in all_results[:15]:

        overall = (
            f"{r['scores']['overall']}%"
            if r["ok"]
            else "FAILED"
        )

        consistency = (
            f"{r['scores'].get('consistency', 0)}%"
            if r["ok"]
            else "-"
        )

        latency = f"{r['latency_ms']}ms"

        print(
            f"  {r['model'][:35]:<35} "
            f"{overall:>10} "
            f"{consistency:>14} "
            f"{latency:>10}"
        )

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    print(f"\nResults saved → {out_file}")
    print("Dashboard     → http://localhost:8000/dashboard\n")


if __name__ == "__main__":
    main()