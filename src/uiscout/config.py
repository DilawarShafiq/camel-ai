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
# uiscout speaks the OpenAI-compatible chat API, which nearly every major LLM
# provider exposes — so this list is "most of the world's LLMs", and OpenRouter
# alone routes to hundreds more (Claude, GPT, Llama, Mistral, Qwen, ...).
# `custom` lets a user point at ANY OpenAI-compatible endpoint we didn't list.
PROVIDERS: dict[str, dict[str, Any]] = {
    "gemini": {
        "label": "Google Gemini  (FREE tier — no credit card)",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "model": "gemini-2.5-flash",
        "key_url": "https://aistudio.google.com/app/apikey",
        "free": True,
    },
    "openrouter": {
        "label": "OpenRouter  (ONE key → hundreds of models: Claude, GPT, Llama…)",
        "base_url": "https://openrouter.ai/api/v1",
        "model": "anthropic/claude-3.5-sonnet",
        "key_url": "https://openrouter.ai/keys",
        "free": False,
    },
    "openai": {
        "label": "OpenAI  (GPT models)",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o",
        "key_url": "https://platform.openai.com/api-keys",
        "free": False,
    },
    "anthropic": {
        "label": "Anthropic Claude",
        "base_url": "https://api.anthropic.com/v1",
        "model": "claude-sonnet-4-5",
        "key_url": "https://console.anthropic.com/settings/keys",
        "free": False,
    },
    "groq": {
        "label": "Groq  (very fast, free tier)",
        "base_url": "https://api.groq.com/openai/v1",
        "model": "llama-3.3-70b-versatile",
        "key_url": "https://console.groq.com/keys",
        "free": True,
    },
    "mistral": {
        "label": "Mistral",
        "base_url": "https://api.mistral.ai/v1",
        "model": "mistral-large-latest",
        "key_url": "https://console.mistral.ai/api-keys",
        "free": False,
    },
    "deepseek": {
        "label": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "key_url": "https://platform.deepseek.com/api_keys",
        "free": False,
    },
    "together": {
        "label": "Together AI  (open models)",
        "base_url": "https://api.together.xyz/v1",
        "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "key_url": "https://api.together.ai/settings/api-keys",
        "free": False,
    },
    "local": {
        "label": "Local model via Ollama / LM Studio  (offline, no key)",
        "base_url": "http://localhost:11434/v1",
        "model": "llama3.1",
        "key_url": None,
        "free": True,
    },
    "custom": {
        "label": "Custom  (any OpenAI-compatible endpoint)",
        "base_url": "",
        "model": "",
        "key_url": None,
        "free": False,
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


def set_brain(provider: str, api_key: str = "", model: str = "",
              base_url: str = "") -> dict[str, Any]:
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider {provider!r}. "
                         f"Choose from: {', '.join(PROVIDERS)}")
    preset = PROVIDERS[provider]
    resolved_base = base_url or preset["base_url"]
    if not resolved_base:
        raise ValueError("This provider needs a base_url (OpenAI-compatible "
                         "endpoint). Pass base_url=...")
    cfg = load_config()
    cfg["brain"] = {
        "provider": provider,
        "base_url": resolved_base,
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
