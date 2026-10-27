"""Multi-provider LLM gateway: routing, fallback, cache, telemetry, and cost estimates."""
from __future__ import annotations

import copy
import hashlib
import json
import logging
import os
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from langchain_groq import ChatGroq
from langchain_mistralai import ChatMistralAI
from langchain_google_genai import ChatGoogleGenerativeAI
from backend.config import settings

logger = logging.getLogger("mailmate.llm_gateway")

# Cache stores only response objects under hashed keys; prompts/email content are not written to disk.
_cache: dict[str, tuple[float, Any]] = {}
_lock = threading.RLock()
_metrics: dict[str, Any] = {
    "requests": 0,
    "successes": 0,
    "failures": 0,
    "cache_hits": 0,
    "cache_misses": 0,
    "providers": defaultdict(lambda: {
        "attempts": 0, "successes": 0, "failures": 0,
        "input_tokens": 0, "output_tokens": 0, "estimated_cost_usd": 0.0,
        "latency_ms_total": 0.0,
    }),
}

PROVIDERS = ("groq", "mistral", "gemini")


def _provider_key(provider: str) -> str:
    return {
        "groq": settings.groq_api_key,
        "mistral": settings.mistral_api_key,
        "gemini": settings.gemini_api_key,
    }[provider]


def _provider_model_name(provider: str) -> str:
    return {
        "groq": settings.groq_model,
        "mistral": settings.mistral_model,
        "gemini": settings.gemini_model,
    }[provider]


def _model(provider: str, temperature: float):
    if provider == "groq":
        return ChatGroq(model=settings.groq_model, api_key=settings.groq_api_key, temperature=temperature)
    if provider == "mistral":
        return ChatMistralAI(model=settings.mistral_model, api_key=settings.mistral_api_key, temperature=temperature)
    if provider == "gemini":
        return ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.gemini_api_key,
            temperature=temperature,
        )
    raise ValueError(f"Unsupported LLM provider: {provider}")


def _configured(provider: str) -> bool:
    return bool(_provider_key(provider).strip())


def _csv(value: str) -> list[str]:
    return [part.strip().lower() for part in value.split(",") if part.strip()]


def provider_order(task: str) -> list[str]:
    """Return task route followed by remaining providers as fallback candidates."""
    task_route = {
        "draft": settings.llm_route_draft,
        "assistant": settings.llm_route_assistant,
        "summarize": settings.llm_route_summarize,
    }.get(task, "")
    if settings.llm_routing_enabled and task_route.strip():
        requested = _csv(task_route)
    else:
        requested = [settings.llm_default_provider.strip().lower()]

    fallback = _csv(settings.llm_provider_order)
    order: list[str] = []
    for name in requested + fallback + list(PROVIDERS):
        if name in PROVIDERS and name not in order:
            order.append(name)
    # Keep the configured default first if a task route was invalid/empty.
    default = settings.llm_default_provider.strip().lower()
    if default in PROVIDERS and default not in order:
        order.insert(0, default)
    return [name for name in order if _configured(name)]


def _jsonable(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if hasattr(value, "model_dump"):
        return _jsonable(value.model_dump())
    if hasattr(value, "content") and hasattr(value, "type"):
        try:
            return {"type": value.type, "content": _jsonable(value.content), "tool_calls": _jsonable(getattr(value, "tool_calls", []))}
        except Exception:
            pass
    return repr(value)


def _cache_key(task: str, provider: str, model_name: str, cache_input: Any) -> str:
    encoded = json.dumps(
        {"task": task, "provider": provider, "model": model_name, "input": _jsonable(cache_input)},
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _cache_get(key: str) -> Any | None:
    if not settings.llm_cache_enabled or settings.llm_cache_ttl_seconds <= 0:
        return None
    now = time.monotonic()
    with _lock:
        entry = _cache.get(key)
        if not entry:
            return None
        expires, value = entry
        if expires <= now:
            _cache.pop(key, None)
            return None
        _metrics["cache_hits"] += 1
        return copy.deepcopy(value)


def _cache_set(key: str, value: Any) -> None:
    if not settings.llm_cache_enabled or settings.llm_cache_ttl_seconds <= 0:
        return
    # Never cache tool-call messages: they may contain provider-specific call IDs.
    if getattr(value, "tool_calls", None):
        return
    with _lock:
        now = time.monotonic()
        expired = [k for k, (expires, _) in _cache.items() if expires <= now]
        for k in expired:
            _cache.pop(k, None)
        max_entries = max(1, settings.llm_cache_max_entries)
        while len(_cache) >= max_entries:
            _cache.pop(next(iter(_cache)))
        _cache[key] = (now + settings.llm_cache_ttl_seconds, copy.deepcopy(value))


def _usage(result: Any) -> tuple[int | None, int | None]:
    if isinstance(result, dict) and result.get("raw") is not None:
        result = result["raw"]
    usage = getattr(result, "usage_metadata", None) or {}
    input_tokens = usage.get("input_tokens") or usage.get("prompt_tokens")
    output_tokens = usage.get("output_tokens") or usage.get("completion_tokens")
    if input_tokens is None or output_tokens is None:
        metadata = getattr(result, "response_metadata", None) or {}
        raw = metadata.get("token_usage") or metadata.get("usage_metadata") or {}
        input_tokens = input_tokens if input_tokens is not None else raw.get("prompt_tokens", raw.get("input_tokens"))
        output_tokens = output_tokens if output_tokens is not None else raw.get("completion_tokens", raw.get("output_tokens"))
    try:
        return (int(input_tokens) if input_tokens is not None else None,
                int(output_tokens) if output_tokens is not None else None)
    except (TypeError, ValueError):
        return None, None


def _cost(provider: str, input_tokens: int | None, output_tokens: int | None) -> float | None:
    if input_tokens is None or output_tokens is None:
        return None
    rates = {
        "groq": (settings.groq_input_cost_per_1m, settings.groq_output_cost_per_1m),
        "mistral": (settings.mistral_input_cost_per_1m, settings.mistral_output_cost_per_1m),
        "gemini": (settings.gemini_input_cost_per_1m, settings.gemini_output_cost_per_1m),
    }[provider]
    return (input_tokens * rates[0] + output_tokens * rates[1]) / 1_000_000


def _record(event: dict[str, Any]) -> None:
    event = {"timestamp": datetime.now(timezone.utc).isoformat(), **event}
    # Logs contain provider/model/latency/token/cost metadata only, never prompts or email content.
    logger.info("llm_gateway_event %s", json.dumps(event, ensure_ascii=False, default=str))
    try:
        log_path = Path(settings.llm_usage_log_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
    except OSError:
        logger.exception("Could not persist LLM usage event")


def invoke_with_fallback(
    *,
    task: str,
    cache_input: Any,
    invoke: Callable[[Any], Any],
    temperature: float = 0.2,
    use_cache: bool = True,
) -> Any:
    """Run a provider-specific invocation, falling back on provider errors."""
    with _lock:
        _metrics["requests"] += 1

    candidates = provider_order(task)
    if not settings.llm_fallback_enabled:
        candidates = candidates[:1]
    if not candidates:
        configured = [p for p in PROVIDERS if _configured(p)]
        raise RuntimeError(
            "No LLM provider API key is configured. Set GROQ_API_KEY, MISTRAL_API_KEY, or GEMINI_API_KEY."
        )

    failures: list[str] = []
    for provider in candidates:
        model_name = _provider_model_name(provider)
        key = _cache_key(task, provider, model_name, cache_input)
        if use_cache:
            cached = _cache_get(key)
            if cached is not None:
                with _lock:
                    _metrics["successes"] += 1
                _record({"event": "cache_hit", "task": task, "provider": provider, "model": model_name})
                return cached
        if use_cache and settings.llm_cache_enabled:
            with _lock:
                _metrics["cache_misses"] += 1

        started = time.perf_counter()
        with _lock:
            _metrics["providers"][provider]["attempts"] += 1
        try:
            result = invoke(_model(provider, temperature))
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            input_tokens, output_tokens = _usage(result)
            cost = _cost(provider, input_tokens, output_tokens)
            with _lock:
                _metrics["successes"] += 1
                bucket = _metrics["providers"][provider]
                bucket["successes"] += 1
                bucket["latency_ms_total"] += latency_ms
                if input_tokens is not None:
                    bucket["input_tokens"] += input_tokens
                if output_tokens is not None:
                    bucket["output_tokens"] += output_tokens
                if cost is not None:
                    bucket["estimated_cost_usd"] += cost
            _record({
                "event": "success", "task": task, "provider": provider, "model": model_name,
                "latency_ms": latency_ms, "input_tokens": input_tokens,
                "output_tokens": output_tokens, "estimated_cost_usd": cost,
            })
            if use_cache:
                _cache_set(key, result)
            return result
        except Exception as exc:
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            failures.append(f"{provider}: {type(exc).__name__}")
            with _lock:
                _metrics["failures"] += 1
                bucket = _metrics["providers"][provider]
                bucket["failures"] += 1
                bucket["latency_ms_total"] += latency_ms
            _record({
                "event": "provider_error", "task": task, "provider": provider,
                "model": model_name, "latency_ms": latency_ms,
                "error_type": type(exc).__name__,
            })
            logger.warning("LLM provider %s failed for task %s (%s); trying fallback", provider, task, type(exc).__name__)

    raise RuntimeError("All configured LLM providers failed. " + "; ".join(failures))


def get_gateway_metrics() -> dict[str, Any]:
    with _lock:
        providers = {}
        for name, stats in _metrics["providers"].items():
            item = dict(stats)
            attempts = item["attempts"]
            item["average_latency_ms"] = round(item["latency_ms_total"] / attempts, 2) if attempts else 0
            item["estimated_cost_usd"] = round(item["estimated_cost_usd"], 8)
            item["configured"] = _configured(name)
            item["model"] = _provider_model_name(name)
            providers[name] = item
        return {
            "default_provider": settings.llm_default_provider,
            "routing_enabled": settings.llm_routing_enabled,
            "fallback_order": _csv(settings.llm_provider_order),
            "cache_enabled": settings.llm_cache_enabled,
            "cache_entries": len(_cache),
            "requests": _metrics["requests"],
            "successes": _metrics["successes"],
            "failures": _metrics["failures"],
            "cache_hits": _metrics["cache_hits"],
            "cache_misses": _metrics["cache_misses"],
            "providers": providers,
            "usage_log_path": settings.llm_usage_log_path,
            "cost_note": "Costs are estimates based on configured per-million-token rates; set rates to current provider pricing.",
        }


def get_gateway_health() -> dict[str, Any]:
    order = provider_order("assistant")
    return {
        "status": "ready" if order else "misconfigured",
        "default_provider": settings.llm_default_provider,
        "available_providers": [p for p in PROVIDERS if _configured(p)],
        "routing_order": order,
        "fallback_enabled": settings.llm_fallback_enabled,
    }


def get_livekit_model_config() -> dict[str, str]:
    """Return OpenAI-compatible connection settings for the LiveKit outer voice LLM.

    The LiveKit session selects one provider at startup. Email tool workflows called by
    the voice agent still use invoke_with_fallback for per-request provider fallback.
    """
    order = provider_order("assistant")
    if not order:
        raise RuntimeError("No LLM provider API key is configured for the LiveKit voice agent.")
    provider = order[0]
    base_urls = {
        "groq": "https://api.groq.com/openai/v1",
        "mistral": "https://api.mistral.ai/v1",
        "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    }
    _record({"event": "livekit_provider_selected", "task": "voice_session", "provider": provider, "model": _provider_model_name(provider)})
    return {
        "model": _provider_model_name(provider),
        "api_key": _provider_key(provider),
        "base_url": base_urls[provider],
    }
