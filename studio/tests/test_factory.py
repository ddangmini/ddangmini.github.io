import math
import random
from datetime import date

from factory import guard, planner, revenue, writer
from factory.cli import build_description, upload_meta

FMT = {"id": "myth-check", "description": "x"}


def test_guard_rejects_near_duplicate():
    s = writer.sample_script(FMT, 0)
    past = [{"title": s.title, "narration": s.narration_text()}]
    problems = guard.check(writer.sample_script(FMT, 1), past, {})
    assert any("similar" in p for p in problems)


def test_guard_passes_fresh_script():
    assert guard.check(writer.sample_script(FMT, 0), [], {}) == []


def test_guard_blocks_ai_voice_on_finance():
    s = writer.sample_script(FMT)
    s.category = "finance"
    assert guard.check(s, [], {"voice": "ai"})
    assert guard.check(s, [], {"voice": "human"}) == []


def test_planner_prefers_winning_format():
    formats = [{"id": "a"}, {"id": "b"}]
    rewards = {"a": [math.log1p(50000)] * 10, "b": [math.log1p(300)] * 10}
    rng = random.Random(1)
    picks = [planner.choose(formats, rewards, rng)["id"] for _ in range(200)]
    assert picks.count("a") > 190


def test_planner_reads_studio_csv(tmp_path):
    p = tmp_path / "a.csv"
    p.write_text("Content,Video title,Views\nabc,제목 1,\"12,345\"\n", encoding="utf-8")
    assert planner.load_views(p) == {"제목 1": 12345.0}


def test_ypp_threshold_doubles_in_2027():
    assert revenue.ypp_threshold(date(2027, 1, 31)) == 10_000_000
    assert revenue.ypp_threshold(date(2027, 2, 1)) == 20_000_000


def test_ads_only_after_joining():
    rows, joined = revenue.simulate(revenue.Assumptions(start=date(2026, 11, 1), views_per_short_start=200_000,
                                                         views_per_short_cap=200_000))
    assert joined is not None
    assert all(r["ads"] == 0 for r in rows if r["date"] < joined)
    assert any(r["ads"] > 0 for r in rows)


def test_upload_meta_discloses_links_and_ai():
    s = writer.sample_script(FMT)
    cfg = {"voice": "ai", "links": [{"label": "도구", "url": "https://example.com"}]}
    meta = upload_meta(s, cfg)
    assert meta["status"]["containsSyntheticMedia"] is True
    assert "https://example.com" in meta["snippet"]["description"]
    assert "수수료" in build_description(s, cfg)
