"""Pre-upload checks against YouTube's inauthentic-content and spam policies.

A channel removed from the Partner Program earns nothing, so a rejected
script is cheaper than a published one that looks mass-produced.
"""
import re

SHINGLE = 5
MAX_NARRATION_SIMILARITY = 0.35
MAX_TITLE_SIMILARITY = 0.6
MIN_PERSPECTIVE_CHARS = 20
AI_PERSONA_BLOCKED = {"health", "finance"}


def _shingles(text, k=SHINGLE):
    t = re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", text.lower())).strip()
    if len(t) < k:
        return {t}
    return {t[i:i + k] for i in range(len(t) - k + 1)}


def similarity(a, b):
    sa, sb = _shingles(a), _shingles(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def check(script, history, cfg):
    """Return a list of problems; empty means the script may be rendered."""
    problems = []
    if len(script.perspective.strip()) < MIN_PERSPECTIVE_CHARS:
        problems.append("perspective too thin: add the channel's own take or test")
    if not script.sources:
        problems.append("no sources listed")
    if cfg.get("voice") == "ai" and script.category in AI_PERSONA_BLOCKED:
        problems.append(f"AI voice on '{script.category}' is not monetizable (YouTube 2026 policy)")
    narration = script.narration_text()
    for past in history:
        s = similarity(narration, past.get("narration", ""))
        if s > MAX_NARRATION_SIMILARITY:
            problems.append(f"narration {s:.0%} similar to '{past.get('title')}'")
            break
    for past in history:
        s = similarity(script.title, past.get("title", ""))
        if s > MAX_TITLE_SIMILARITY:
            problems.append(f"title {s:.0%} similar to '{past.get('title')}'")
            break
    return problems
