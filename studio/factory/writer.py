"""Script generation with Claude (structured output), plus an offline sample."""
import json

from .models import Beat, Script

MODEL = "claude-opus-5-5"

SYSTEM = """You write scripts for a YouTube Shorts channel.
Every script must be original: built around one specific, verifiable fact or test,
with the channel's own perspective (an opinion, a comparison, a small experiment)
that a generic template could not produce. Never invent facts; list sources.
Keep it 25-45 seconds when read aloud. Write in the channel's language."""


def build_prompt(cfg, fmt, recent_titles):
    avoid = "\n".join(f"- {t}" for t in recent_titles[-30:]) or "(none yet)"
    return (
        f"Channel niche: {cfg['niche']}\n"
        f"Language: {cfg.get('language', 'ko')}\n"
        f"Audience: {cfg.get('audience', 'general')}\n"
        f"Format id: {fmt['id']}\nFormat description: {fmt['description']}\n"
        f"Topics already covered (do not repeat or paraphrase):\n{avoid}\n\n"
        "Write one new script for this format."
    )


def write_script(cfg, fmt, recent_titles):
    import anthropic

    client = anthropic.Anthropic()
    response = client.beta.messages.parse(
        model=cfg.get("model", MODEL),
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": "medium"},
        system=SYSTEM,
        messages=[{"role": "user", "content": build_prompt(cfg, fmt, recent_titles)}],
        output_format=Script,
    )
    if response.stop_reason == "refusal":
        raise RuntimeError(f"Claude declined this topic: {response.stop_details}")
    script = response.parsed_output
    script.format = fmt["id"]
    return script


def sample_script(fmt, n=0):
    """Deterministic script for dry runs and tests (no API call)."""
    return Script(
        format=fmt["id"],
        category="science",
        hook=f"샘플 {n}: 바나나는 사실 방사능을 띱니다.",
        beats=[
            Beat(on_screen="바나나 = 칼륨-40", narration="바나나에는 칼륨이 많고, 그중 일부가 방사성 동위원소 칼륨-40입니다."),
            Beat(on_screen="얼마나 위험할까?", narration="하지만 바나나 하나의 선량은 흉부 엑스레이의 천분의 일도 안 됩니다."),
            Beat(on_screen="바나나 등가 선량", narration="그래서 과학자들은 이걸 '바나나 등가 선량'이라는 농담 섞인 단위로 씁니다."),
        ],
        perspective=f"제가 계산해 보니 엑스레이 한 번과 같아지려면 바나나를 한 번에 수백 개 먹어야 합니다. ({n})",
        cta="다음엔 어떤 음식을 재볼까요? 댓글로 알려주세요.",
        title=f"바나나가 방사능을 띤다고? #{n}",
        description="바나나 등가 선량(BED)에 대한 짧은 설명.",
        tags=["과학", "바나나", "방사능"],
        thumbnail_text="바나나 방사능?",
        sources=["https://en.wikipedia.org/wiki/Banana_equivalent_dose", "US EPA radiation doses"],
    )


def dump(script):
    return json.dumps(script.model_dump(), ensure_ascii=False, indent=2)
