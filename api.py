# api.py — FastAPI app comparing JD generation & skill suggestion quality
# across all available Groq models, in parallel.
#
# Run:  uvicorn api:app --reload
# Swagger UI:  http://localhost:8000/docs

import asyncio
import json
import os
import re
import time

from dotenv import load_dotenv
from fastapi import FastAPI
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from models import MODELS_TO_TEST, estimate_cost_usd
from prompts import (
    SKILL_SYSTEM_PROMPT,
    JD_SYSTEM_PROMPT,
    build_skill_user_prompt,
    build_jd_user_prompt,
)

# ── Setup (same Groq client config as the rest of the project) ─────────────

load_dotenv()

client = AsyncOpenAI(
    api_key=os.getenv("API_KEY"),
    base_url="https://api.groq.com/openai/v1",
)

app = FastAPI(
    title="iFocus JD & Skill Model Comparator",
    description=(
        "Compare JD generation and skill suggestion quality across all "
        "available Groq models. Each request fans out to every model in "
        "parallel and reports latency, token usage and estimated cost."
    ),
    version="2.0.0",
)


# ── Schemas ────────────────────────────────────────────────────────────────


class JobInput(BaseModel):
    """Single input schema shared by all three comparison endpoints.
    The AI generates skills from scratch — no recruiter skill lists needed."""
    title: str = "Data Scientist"
    job_family: str = "Developer"
    min_exp: int = 4
    max_exp: int = 5
    salary_lpa: float = 4
    locations: list[str] = Field(
        default_factory=lambda: ["bangalore", "mumbai", "hyderabad"]
    )
    company_name: str = "iFocus"
    company_description: str = (
        "iFocus builds analytics tools for mid-market businesses across India."
    )
    demand_type: str = "Permanent"


class ModelResult(BaseModel):
    model: str
    response: str | None = None
    latency_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_estimate_usd: float | None = None
    error: str | None = None


class FullModelResult(BaseModel):
    model: str
    skill: ModelResult | None = None
    jd: ModelResult | None = None
    error: str | None = None


# ── Helpers ────────────────────────────────────────────────────────────────


def extract_json(text: str) -> dict:
    """Best-effort parse of a model's JSON response (mirrors run_comparison)."""
    clean = re.sub(r"```(?:json)?\s*", "", text or "").strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]+\}", clean)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return {"_parse_error": True}


async def call_model(
    model_id: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    json_mode: bool,
    max_tokens: int = 2000,
) -> ModelResult:
    """Call one model, timing it and capturing tokens/cost. Never raises."""
    t0 = time.time()
    try:
        kwargs = dict(
            model=model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        resp = await client.chat.completions.create(**kwargs)

        latency_ms = round((time.time() - t0) * 1000)
        raw_text = resp.choices[0].message.content or ""

        usage = getattr(resp, "usage", None)
        input_tokens = getattr(usage, "prompt_tokens", 0) or 0
        output_tokens = getattr(usage, "completion_tokens", 0) or 0

        if not raw_text:
            return ModelResult(
                model=model_id,
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_estimate_usd=estimate_cost_usd(model_id, input_tokens, output_tokens),
                error="Empty response",
            )

        return ModelResult(
            model=model_id,
            response=raw_text,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_estimate_usd=estimate_cost_usd(model_id, input_tokens, output_tokens),
            error=None,
        )

    except Exception as exc:
        return ModelResult(
            model=model_id,
            latency_ms=round((time.time() - t0) * 1000),
            error=str(exc),
        )


async def _run_skill_then_jd(
    model_id: str, payload: JobInput
) -> tuple[ModelResult, ModelResult | None]:
    """Generate skills from job info, then generate JD using those skills.
    Returns (skill_result, jd_result). jd_result is None if skills failed."""
    skill_prompt = build_skill_user_prompt(
        title=payload.title,
        job_family=payload.job_family,
        min_exp=payload.min_exp,
        max_exp=payload.max_exp,
        salary_lpa=payload.salary_lpa,
        locations=payload.locations,
    )
    skill_res = await call_model(
        model_id, SKILL_SYSTEM_PROMPT, skill_prompt,
        temperature=0.3, json_mode=True,
    )

    if skill_res.error:
        return skill_res, None

    parsed = extract_json(skill_res.response or "")
    # Fall back to sensible defaults if the model returned malformed JSON
    required_skills = parsed.get("required_skills") or [payload.title.split()[0]]
    optional_skills = parsed.get("optional_skills") or []

    jd_prompt = build_jd_user_prompt(
        title=payload.title,
        company_name=payload.company_name,
        company_description=payload.company_description,
        job_family=payload.job_family,
        min_exp=payload.min_exp,
        max_exp=payload.max_exp,
        salary_lpa=payload.salary_lpa,
        locations=payload.locations,
        required_skills=required_skills,
        optional_skills=optional_skills,
        demand_type=payload.demand_type,
    )
    jd_res = await call_model(
        model_id, JD_SYSTEM_PROMPT, jd_prompt,
        temperature=0.7, json_mode=False,
    )

    return skill_res, jd_res


# ── Endpoints ──────────────────────────────────────────────────────────────


@app.get("/api/models")
async def get_models():
    """List the Groq models that each comparison request is run against."""
    return {"models": MODELS_TO_TEST, "count": len(MODELS_TO_TEST)}


@app.post("/api/compare/skills")
async def compare_skills(payload: JobInput):
    """Generate skills from scratch for all models in parallel.
    No recruiter skill lists — the model figures out what's appropriate."""
    user_prompt = build_skill_user_prompt(
        title=payload.title,
        job_family=payload.job_family,
        min_exp=payload.min_exp,
        max_exp=payload.max_exp,
        salary_lpa=payload.salary_lpa,
        locations=payload.locations,
    )

    results = await asyncio.gather(
        *(
            call_model(m, SKILL_SYSTEM_PROMPT, user_prompt, temperature=0.3, json_mode=True)
            for m in MODELS_TO_TEST
        )
    )

    return {
        "results": [r.model_dump() for r in results],
        "input_used": payload.model_dump(),
    }


@app.post("/api/compare/jd")
async def compare_jd(payload: JobInput):
    """Generate skills internally then write a JD — all from job info alone.
    Each model runs its own skill generation step before writing the JD.
    Response contains only the final JD per model (combined latency/tokens)."""

    async def _jd_only(model_id: str) -> ModelResult:
        skill_res, jd_res = await _run_skill_then_jd(model_id, payload)
        if jd_res is None:
            # Skills step failed — surface the error on the JD result
            return ModelResult(
                model=model_id,
                latency_ms=skill_res.latency_ms,
                input_tokens=skill_res.input_tokens,
                output_tokens=skill_res.output_tokens,
                cost_estimate_usd=skill_res.cost_estimate_usd,
                error=f"Skill step failed: {skill_res.error}",
            )
        # Combine metrics from both calls
        total_in = (skill_res.input_tokens or 0) + (jd_res.input_tokens or 0)
        total_out = (skill_res.output_tokens or 0) + (jd_res.output_tokens or 0)
        total_lat = (skill_res.latency_ms or 0) + (jd_res.latency_ms or 0)
        return ModelResult(
            model=model_id,
            response=jd_res.response,
            latency_ms=total_lat,
            input_tokens=total_in,
            output_tokens=total_out,
            cost_estimate_usd=estimate_cost_usd(model_id, total_in, total_out),
            error=jd_res.error,
        )

    results = await asyncio.gather(*(_jd_only(m) for m in MODELS_TO_TEST))

    return {
        "results": [r.model_dump() for r in results],
        "input_used": payload.model_dump(),
    }


@app.post("/api/compare/full")
async def compare_full(payload: JobInput):
    """Full pipeline for every model in parallel:
    1. Generate skills from job info
    2. Use those skills to write the JD
    Returns both skill output and JD output per model."""

    async def _full(model_id: str) -> FullModelResult:
        skill_res, jd_res = await _run_skill_then_jd(model_id, payload)
        if jd_res is None:
            return FullModelResult(
                model=model_id,
                skill=skill_res,
                jd=None,
                error=f"Skill step failed: {skill_res.error}",
            )
        return FullModelResult(model=model_id, skill=skill_res, jd=jd_res)

    results = await asyncio.gather(*(_full(m) for m in MODELS_TO_TEST))

    return {
        "results": [r.model_dump() for r in results],
        "input_used": payload.model_dump(),
    }


@app.get("/")
async def root():
    return {
        "service": "iFocus JD & Skill Model Comparator",
        "docs": "/docs",
        "endpoints": [
            "GET  /api/models",
            "POST /api/compare/skills",
            "POST /api/compare/jd",
            "POST /api/compare/full",
        ],
    }
