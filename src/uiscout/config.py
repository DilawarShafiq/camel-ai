"""User config + brain selection — the OpenClaw-style setup model.

uiscout keeps a small config at ~/.uiscout/config.json holding which LLM "brain"
to use and its API key. Defaults to a FREE bring-your-own-key provider (Google
Gemini's free tier), so a non-technical user pastes one free key in the wizard
and never pays — no hosted backend, no per-token cost to you.

All presets speak the OpenAI-compatible chat API, so a single provider class
(uiscout.agent.OpenAICompatibleProvider) drives any of them.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

CONFIG_DIR = Path(os.environ.get("UISCOUT_HOME", Path.home() / ".uiscout"))
CONFIG_PATH = CONFIG_DIR / "config.json"

# Each preset: where to get a key, the endpoint, and a sensible default model
# (all user-overridable in the wizard).
PROVIDERS: dict[str, dict[str, Any]] = {
    "gemini": {
        "label": "Google Gemini  (FREE tier — no credit card)",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "model": "gemini-2.5-flash",
        "key_url": "https://aistudio.google.com/app/apikey",
        "free": True,
    },
    "openrouter": {
        "label": "OpenRouter  (any model, incl. Claude/GPT)",
        "base_url": "https://openrouter.ai/api/v1",
        "model": "anthropic/claude-3.5-sonnet",
        "key_url": "https://openrouter.ai/keys",
        "free": False,
    },
    "openai": {
        "label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o",
        "key_url": "https://platform.openai.com/api-keys",
        "free": False,
    },
    "local": {
        "label": "Local model via Ollama  (offline, no key)",
        "base_url": "http://localhost:11434/v1",
        "model": "llama3.1",
        "key_url": None,
        "free": True,
    },
}

DEFAULT_PROVIDER = "gemini"


def load_config() -> dict[str, Any]:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_config(cfg: dict[str, Any]) -> Path:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    try:  # best-effort: keep the key file private on POSIX
        os.chmod(CONFIG_PATH, 0o600)
    except Exception:
        pass
    return CONFIG_PATH


def set_brain(provider: str, api_key: str = "", model: str = "") -> dict[str, Any]:
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider {provider!r}. "
                         f"Choose from: {', '.join(PROVIDERS)}")
    preset = PROVIDERS[provider]
    cfg = load_config()
    cfg["brain"] = {
        "provider": provider,
        "base_url": preset["base_url"],
        "model": model or preset["model"],
        "api_key": api_key or "not-needed",
    }
    save_config(cfg)
    return cfg["brain"]


def get_brain() -> dict[str, Any] | None:
    """Return the configured brain, honoring env overrides for CI/advanced use."""
    env_key = os.environ.get("UISCOUT_API_KEY")
    if env_key:
        prov = os.environ.get("UISCOUT_PROVIDER", DEFAULT_PROVIDER)
        preset = PROVIDERS.get(prov, PROVIDERS[DEFAULT_PROVIDER])
        return {"provider": prov, "base_url": preset["base_url"],
                "model": os.environ.get("UISCOUT_MODEL", preset["model"]),
                "api_key": env_key}
    return load_config().get("brain")


def is_configured() -> bool:
    b = get_brain()
    return bool(b and (b.get("api_key") not in (None, "", "not-needed")
                       or b.get("provider") == "local"))
