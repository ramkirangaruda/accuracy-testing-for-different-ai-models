import os
import json
import time

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("API_KEY"),
    base_url="https://api.groq.com/openai/v1",
)

# stable + cheap judge model
JUDGE_MODEL = "llama-3.1-8b-instant"

JUDGE_MAX_RETRIES = 3
JUDGE_BACKOFF_SECONDS = 2
MAX_GENERATED_CHARS = 3000
MAX_JUDGE_TOKENS = 400


def safe_json_extract(text):

    if not text:
        raise ValueError("Empty judge response")

    cleaned = text.strip()

    if cleaned.startswith("```"):
        cleaned = cleaned.replace("```json", "").replace("```", "").strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1

    if start == -1 or end <= start:
        raise ValueError("No JSON object found")

    candidate = cleaned[start:end]

    return json.loads(candidate)


def is_rate_limit_error(exc: Exception) -> bool:

    msg = str(exc).lower()

    return any(
        token in msg
        for token in [
            "rate limit",
            "429",
            "quota",
            "too many requests",
        ]
    )


def evaluate_output(scenario, generated_output):

    # prevent gigantic prompts
    generated_output = generated_output[:MAX_GENERATED_CHARS]

    prompt = f"""
You are evaluating AI-generated software test cases.

Evaluate STRICTLY according to the rubric.

Scenario:
Name: {scenario['name']}
Feature: {scenario['feature']}
Type: {scenario['type']}
Difficulty: {scenario['difficulty']}

Generated Test Cases:
{generated_output}

Rubric:
- technical_correctness: yes | partial | no
- automation_ready: yes | partial | no
    * yes ONLY if explicit endpoints, payloads, request structure, and executable assertions exist
    * partial if some are present but missing executable detail
    * no if manual QA, vague checks, or missing structure
- assertions_testable: yes | partial | no
- oracle_correct: yes | partial | no
- edge_case_realism: excellent | good | partial | poor

Strict penalties:
- Vague assertions, manual workflows, oracle inversion, ambiguity failures
- Hallucinated features or endpoints

Return ONLY valid JSON.

Schema:
{{
    "evaluation_status": "success",
    "technical_correctness": "",
    "automation_ready": "",
    "assertions_testable": "",
    "oracle_correct": "",
    "edge_case_realism": "",
    "summary": "",
    "strengths": [],
    "weaknesses": [],
    "critical_failures": [],
    "suggested_tags": []
}}
"""

    print(f"[JUDGE] Using model: {JUDGE_MODEL}")

    last_error = None

    for attempt in range(1, JUDGE_MAX_RETRIES + 1):
        try:

            t0 = time.time()

            response = client.chat.completions.create(
                model=JUDGE_MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0,
                max_tokens=MAX_JUDGE_TOKENS,
            )

            latency_ms = round((time.time() - t0) * 1000)

            content = response.choices[0].message.content

            parsed = safe_json_extract(content)

            parsed["evaluation_status"] = "success"
            parsed["judge_latency_ms"] = latency_ms
            parsed["judge_model"] = JUDGE_MODEL

            return parsed

        except Exception as e:

            last_error = e

            if is_rate_limit_error(e) and attempt < JUDGE_MAX_RETRIES:
                print(
                    "[JUDGE] Rate limit hit; "
                    f"retrying in {JUDGE_BACKOFF_SECONDS}s "
                    f"(attempt {attempt}/{JUDGE_MAX_RETRIES})"
                )
                time.sleep(JUDGE_BACKOFF_SECONDS * attempt)
                continue

            break

    return {
        "evaluation_status": "judge_failed",
        "judge_model": JUDGE_MODEL,
        "judge_latency_ms": None,
        "technical_correctness": "unknown",
        "automation_ready": "unknown",
        "assertions_testable": "unknown",
        "oracle_correct": "unknown",
        "edge_case_realism": "unknown",
        "summary": f"Judge failed: {str(last_error)}",
        "strengths": [],
        "weaknesses": [
            "Judge evaluation could not be completed"
        ],
        "critical_failures": [
            str(last_error)
        ],
        "suggested_tags": [
            "judge-failure"
        ]
    }