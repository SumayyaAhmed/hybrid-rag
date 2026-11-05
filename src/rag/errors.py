"""Errors shared across the app."""


class UpstreamUnavailable(RuntimeError):
    """A hosted model (Voyage or Gemini) can't serve us right now: rate limit, quota used up, or server busy.

    Temporary and not our bug. The API turns it into HTTP 503 "try again later" (spec 10); the CLI/chat print the message.
    """
