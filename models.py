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