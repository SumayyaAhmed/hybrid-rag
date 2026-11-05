"""Thin Gemini wrapper. Swapping LLM provider only means changing this file."""

import time
from functools import cache

from google import genai
from google.genai import errors, types

from rag.config import settings
from rag.errors import UpstreamUnavailable


@cache
def client() -> genai.Client:
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is empty. Add it to .env (get one at aistudio.google.com/apikey).")
    return genai.Client(api_key=settings.gemini_api_key)


def complete(system: str, user: str, retries: int = 4) -> str:
    config = types.GenerateContentConfig(
        system_instruction=system,
        temperature=settings.llm_temperature,
        max_output_tokens=settings.llm_max_tokens,
        # Gemini 2.5 "thinks" first, and thinking tokens count toward max_output_tokens -> cut-off answers.
        # Grounded answers from given sources don't need it, so turn it off.
        thinking_config=types.ThinkingConfig(thinking_budget=0),
    )
    for attempt in range(retries):
        try:
            response = client().models.generate_content(model=settings.llm_model, contents=user, config=config)
            return response.text or ""
        except errors.ClientError as e:
            if e.code != 429 or attempt == retries - 1:
                raise
            if "PerDay" in str(e):  # daily free-tier quota: waiting seconds won't help
                raise UpstreamUnavailable(f"Gemini daily free-tier quota for {settings.llm_model} is used up; it resets in ~24h.") from e
            reason = "rate limit hit"
        except errors.ServerError as e:  # 503 "high demand" / 500: Google-side and usually temporary
            if attempt == retries - 1:
                raise UpstreamUnavailable(f"Gemini is unavailable right now ({e.code}); try again in a minute.") from e
            reason = f"server busy ({e.code})"
        wait = 5 * 2**attempt  # back off 5s, 10s, 20s
        print(f"Gemini {reason}, retrying in {wait}s...")
        time.sleep(wait)
    raise AssertionError("unreachable")
