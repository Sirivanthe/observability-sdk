"""
observability_sdk.backend.middleware
--------------------------------------
FastAPI middleware that intercepts outbound LLM HTTP calls and records them.

HOW IT WORKS
------------
Rather than patching httpx globally (fragile), we wrap the LLM client's
`generate()` method via a lightweight decorator. This is more reliable
across different LLM backends (Ollama, Gemini REST, OpenAI-compatible).

Usage
-----
    from observability_sdk import ObservabilityMiddleware
    app.add_middleware(ObservabilityMiddleware)

The middleware also captures request metadata (path, method) so you can
correlate which API endpoint triggered which LLM call.
"""

import time
import logging
import contextvars
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from .store import record_llm_call

logger = logging.getLogger("observability_sdk.middleware")

# Context var so nested code can attach the current HTTP path to LLM calls
_current_endpoint: contextvars.ContextVar[str] = contextvars.ContextVar(
    "_obs_current_endpoint", default="unknown"
)


def get_current_endpoint() -> str:
    return _current_endpoint.get()


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """
    Lightweight request-tracking middleware.

    Records basic request metrics and sets the endpoint context so LLM
    calls made during a request are tagged with the originating route.
    """

    async def dispatch(self, request: Request, call_next):
        token = _current_endpoint.set(request.url.path)
        start = time.perf_counter()
        try:
            response = await call_next(request)
            return response
        finally:
            _current_endpoint.reset(token)


# ── LLM call wrapper ──────────────────────────────────────────────────────────

def track_llm_call(func):
    """
    Async decorator that wraps any `generate(prompt, ...) -> dict` function
    and records its metrics to the observability store.

    The wrapped function must return a dict with keys:
        response, prompt_tokens, completion_tokens, model_name

    Usage:
        from observability_sdk import track_llm_call

        @track_llm_call
        async def _call_gemini(system, prompt):
            ...
    """
    import functools

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.perf_counter()
        caller = get_current_endpoint()
        try:
            result = await func(*args, **kwargs)
            latency_ms = (time.perf_counter() - start) * 1000

            model = result.get("model_name", "unknown")
            prompt_tokens = result.get("prompt_tokens", 0)
            completion_tokens = result.get("completion_tokens", 0)

            # Infer provider from model name
            provider = _infer_provider(model)

            record_llm_call(
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=round(latency_ms, 1),
                provider=provider,
                status="success",
                caller=caller,
            )
            return result

        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            record_llm_call(
                model="unknown",
                prompt_tokens=0,
                completion_tokens=0,
                latency_ms=round(latency_ms, 1),
                provider="unknown",
                status="error",
                error_msg=str(exc)[:500],
                caller=caller,
            )
            raise

    return wrapper


def track_llm_generate(model_name_attr: str = "model_name", provider_attr: str = None):
    """
    Class-method decorator for LLM client classes that have a `generate()` method.

    Usage:
        class GeminiLLMClient:
            model_name = "gemini-2.5-flash"

            @track_llm_generate(model_name_attr="model_name")
            async def generate(self, prompt, context="", system_prompt=""):
                ...
    """
    def decorator(func):
        import functools

        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            start = time.perf_counter()
            caller = get_current_endpoint()
            model = getattr(self, model_name_attr, "unknown")
            provider = provider_attr or _infer_provider(model)

            try:
                result = await func(self, *args, **kwargs)
                latency_ms = (time.perf_counter() - start) * 1000

                record_llm_call(
                    model=result.get("model_name", model),
                    prompt_tokens=result.get("prompt_tokens", 0),
                    completion_tokens=result.get("completion_tokens", 0),
                    latency_ms=round(latency_ms, 1),
                    provider=provider,
                    status="success",
                    caller=caller,
                )
                return result

            except Exception as exc:
                latency_ms = (time.perf_counter() - start) * 1000
                record_llm_call(
                    model=model,
                    prompt_tokens=0,
                    completion_tokens=0,
                    latency_ms=round(latency_ms, 1),
                    provider=provider,
                    status="error",
                    error_msg=str(exc)[:500],
                    caller=caller,
                )
                raise

        return wrapper
    return decorator


def _infer_provider(model: str) -> str:
    m = model.lower()
    if "gemini" in m:
        return "gemini"
    if "gpt" in m or "o1" in m or "o3" in m:
        return "openai"
    if "claude" in m or "sonnet" in m or "haiku" in m or "opus" in m:
        return "anthropic"
    if "llama" in m or "mistral" in m or "qwen" in m or "phi" in m or "nomic" in m:
        return "ollama"
    if "moonshot" in m or "kimi" in m:
        return "kimi"
    return "unknown"
