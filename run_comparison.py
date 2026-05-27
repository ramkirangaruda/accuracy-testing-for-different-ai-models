#!/usr/bin/env python3
from opik import track
from opik import opik_context
from evaluations import EVALUATIONS
import argparse
import json
import os
import re
import time
import difflib
from judge import evaluate_output

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from models import AVAILABLE_MODELS
from prompt_template import SYSTEM_PROMPT, build_user_prompt
from scorer import score
from scenarios import SCENARIOS

REPEAT_COUNT = 2

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


def build_generation_failure_eval(reason: str) -> dict:

    return {
        "evaluation_status": "generation_failed",
        "technical_correctness": "unknown",
        "automation_ready": "unknown",
        "assertions_testable": "unknown",
        "oracle_correct": "unknown",
        "edge_case_realism": "unknown",
        "summary": "Generation failed; judge not called",
        "strengths": [],
        "weaknesses": ["No output to evaluate"],
        "critical_failures": [reason],
        "suggested_tags": ["generation-failure"],
        "judge_model": None,
        "judge_latency_ms": None,
    }


def build_skipped_eval() -> dict:

    return {
        "evaluation_status": "skipped",
        "technical_correctness": "unknown",
        "automation_ready": "unknown",
        "assertions_testable": "unknown",
        "oracle_correct": "unknown",
        "edge_case_realism": "unknown",
        "summary": "Evaluation skipped for repeat run",
        "strengths": [],
        "weaknesses": [],
        "critical_failures": [],
        "suggested_tags": ["evaluation-skipped"],
        "judge_model": None,
        "judge_latency_ms": None,
    }


def build_unknown_eval(reason: str) -> dict:

    return {
        "evaluation_status": "unknown",
        "technical_correctness": "unknown",
        "automation_ready": "unknown",
        "assertions_testable": "unknown",
        "oracle_correct": "unknown",
        "edge_case_realism": "unknown",
        "summary": f"Evaluation unknown: {reason}",
        "strengths": [],
        "weaknesses": [],
        "critical_failures": [reason],
        "suggested_tags": ["evaluation-unknown"],
        "judge_model": None,
        "judge_latency_ms": None,
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

@track
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

    evaluation = build_unknown_eval("initial state")
    result = call_model(model_id, user_prompt)
    if result.get("ok") and not result.get("raw_text"):
        result["ok"] = False
        result["error"] = "Empty response"
    if result.get("ok") and result.get("raw_text"):

        print(
            "  [GENERATION] "
            f"status=success model={model_id} "
            f"latency_ms={result['latency_ms']}"
        )

        # only judge first repeat
        if run_number == 1:

            evaluation = evaluate_output(
                scenario,
                result["raw_text"]
            )

        else:

            evaluation = build_skipped_eval()

    else:

        failure_reason = result.get("error") or "Empty response"

        print(
            "  [GENERATION] "
            f"status=failed model={model_id} "
            f"latency_ms={result.get('latency_ms')}"
        )

        evaluation = build_generation_failure_eval(failure_reason)

    print(
        "  [EVALUATION] "
        f"status={evaluation.get('evaluation_status')} "
        f"judge_model={evaluation.get('judge_model')} "
        f"judge_latency_ms={evaluation.get('judge_latency_ms')}"
    )

    try:
        opik_context.update_current_trace(
            metadata={
                "model": model_id,
                "scenario": scenario["name"],
                "domain": scenario["domain"],
                "difficulty": scenario["difficulty"],
                "run_number": run_number,
                "evaluation": evaluation
            },
            tags=evaluation.get("suggested_tags", [])
        )
    except Exception as exc:
        print(f"  [OPIK] update failed: {exc}")

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
            "evaluation": evaluation,
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

    try:
        scores = score(
            parsed,
            feature,
            requested_count
        )
    except Exception as exc:
        print(f"  [SCORER ERROR] {exc}")
        scores = {
            "overall": 0,
            "coverage": 0,
            "relevance": 0,
            "structure": 0,
            "edge_cases": 0,
            "clarity": 0,
            "consistency": 0,
            "count": 0,
            "scoring_failed": True,
            "scoring_error": str(exc),
        }

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
        "evaluation": evaluation,
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

    if args.workers > 1:
        print(
            "  [WARN] Judge is rate-limit heavy; "
            "recommend --workers 1 for judge-heavy runs."
        )

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