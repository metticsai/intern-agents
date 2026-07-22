import os
import json


def get_model(tier: str = "primary"):
    """Return the configured LLM model based on config.json.

    tier='primary' → stronger model (Sonnet / Gemini Flash) for generation and extraction
    tier='fast'    → cheaper model (Haiku / Gemini Flash) for validation and routing

    Switch providers by changing 'provider' in config.json:
      'anthropic' → Claude Sonnet 4.6 / Haiku 4.5 (Anthropic API)
      'gemini'    → Gemini 2.5 Flash (Google API via LiteLLM)
    """
    config = json.load(open("config.json"))
    provider = config["ai_generation"]["provider"]

    if provider == "anthropic":
        from strands.models.anthropic import AnthropicModel

        if tier == "primary":
            model_id = "claude-sonnet-4-6"
            max_tokens = 8192
            temperature = 0.8
        else:
            model_id = "claude-haiku-4-5-20251001"
            max_tokens = 4096
            temperature = 0.3

        return AnthropicModel(
            client_args={"api_key": os.getenv("ANTHROPIC_API_KEY")},
            model_id=model_id,
            max_tokens=max_tokens,
            params={"temperature": temperature},
        )

    elif provider == "gemini":
        from strands.models.litellm import LiteLLMModel

        gemini_model = config["ai_generation"]["model"]
        return LiteLLMModel(
            model_id=f"gemini/{gemini_model}",
            max_tokens=8192 if tier == "primary" else 4096,
            temperature=0.8 if tier == "primary" else 0.3,
            client_args={"api_key": os.getenv("GEMINI_API_KEY")},
        )

    else:
        raise ValueError(
            f"Unknown provider '{provider}' in config.json. "
            "Supported: 'anthropic', 'gemini'"
        )
