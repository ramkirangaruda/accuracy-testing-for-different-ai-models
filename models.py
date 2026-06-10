# models.py — all available models in your API key
# Edit this list to add/remove models

AVAILABLE_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "qwen/qwen3-32b",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "allam-2-7b",
    "groq/compound",
    "groq/compound-mini",
]

# Models that only do speech-to-text or safeguarding — skip for text generation
SKIP_MODELS = [
    "whisper-large-v3-turbo",
    "whisper-large-v3",
    "meta-llama/llama-prompt-guard-2-86m",
    "meta-llama/llama-prompt-guard-2-22m",
    "openai/gpt-oss-safeguard-20b",
    "canopylabs/orpheus-v1-english",
    "canopylabs/orpheus-arabic-saudi",
]

# Models actually used for the JD / skill comparison (text generation only).
MODELS_TO_TEST = [m for m in AVAILABLE_MODELS if m not in SKIP_MODELS]

# Cost per 1M tokens, in USD: (input_rate, output_rate).
# Models without an entry are billed at 0.0 (e.g. groq/compound, allam-2-7b)
# so cost_estimate_usd stays a best-effort number rather than failing.
PRICING = {
    "llama-3.1-8b-instant": (0.05, 0.08),
    "llama-3.3-70b-versatile": (0.59, 0.79),
    "openai/gpt-oss-120b": (0.15, 0.60),
    "openai/gpt-oss-20b": (0.075, 0.30),
    "qwen/qwen3-32b": (0.29, 0.59),
    "meta-llama/llama-4-scout-17b-16e-instruct": (0.11, 0.34),
}


def estimate_cost_usd(model_id: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate request cost in USD from token counts and PRICING rates."""
    input_rate, output_rate = PRICING.get(model_id, (0.0, 0.0))
    cost = (input_tokens / 1_000_000) * input_rate + (
        output_tokens / 1_000_000
    ) * output_rate
    return round(cost, 6)