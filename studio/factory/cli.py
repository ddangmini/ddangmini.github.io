"""Command line entry: python -m factory {make,plan,forecast}."""
import argparse
import json
import random
import sys
from datetime import date, datetime
from pathlib import Path

from . import guard, planner, revenue, writer
from .render import render

ROOT = Path(__file__).resolve().parent.parent
HISTORY = ROOT / "data" / "history.jsonl"
OUTBOX = ROOT / "outbox"


def load_cfg(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_history():
    if not HISTORY.exists():
        return []
    return [json.loads(l) for l in HISTORY.read_text(encoding="utf-8").splitlines() if l.strip()]


def append_history(entry):
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def build_description(script, cfg):
    parts = [script.description.strip(), ""]
    links = cfg.get("links", [])
    if links:
        parts += [f"{l['label']}: {l['url']}" for l in links]
        parts += [cfg.get("link_disclosure", "※ 위 링크는 제휴 링크로, 구매 시 채널이 수수료를 받을 수 있습니다."), ""]
    if script.sources:
        parts += ["출처:"] + [f"- {s}" for s in script.sources] + [""]
    parts.append(" ".join("#" + t.replace(" ", "") for t in script.tags[:3]) + " #Shorts")
    return "\n".join(parts)[:4900]


def upload_meta(script, cfg):
    """Fields mapped 1:1 onto the YouTube videos.insert body used by the n8n workflow."""
    return {
        "snippet": {
            "title": script.title[:100],
            "description": build_description(script, cfg),
            "tags": script.tags[:15],
            "categoryId": cfg.get("category_id", "27"),
            "defaultLanguage": cfg.get("language", "ko"),
        },
        "status": {
            "privacyStatus": cfg.get("privacy", "private"),
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": cfg.get("voice") == "ai",
        },
        "pinned_comment": cfg.get("pinned_comment", ""),
    }


def cmd_make(args):
    cfg = load_cfg(args.config)
    history = load_history()
    rewards = {}
    if args.analytics:
        rewards = planner.rewards_by_format(history, planner.load_views(args.analytics))
    made = 0
    attempts = 0
    while made < args.count and attempts < args.count * 3:
        attempts += 1
        fmt = planner.choose(cfg["formats"], rewards)
        titles = [h["title"] for h in history]
        script = writer.sample_script(fmt, len(history)) if args.dry_run else writer.write_script(cfg, fmt, titles)
        problems = guard.check(script, history, cfg)
        if problems:
            print(f"[skip] {script.title}: " + "; ".join(problems), file=sys.stderr)
            continue
        vid = datetime.now().strftime("%Y%m%d-%H%M%S") + f"-{made}"
        out = OUTBOX / vid
        out.mkdir(parents=True, exist_ok=True)
        (out / "script.json").write_text(writer.dump(script), encoding="utf-8")
        video, thumb, seconds = render(script, cfg, out)
        (out / "meta.json").write_text(json.dumps(upload_meta(script, cfg), ensure_ascii=False, indent=2), encoding="utf-8")
        (out / "READY").touch()  # n8n watches for this marker
        entry = {"id": vid, "format": fmt["id"], "title": script.title, "narration": script.narration_text(),
                 "seconds": round(seconds, 1), "created": date.today().isoformat()}
        append_history(entry)
        history.append(entry)
        made += 1
        print(f"[ok] {out} ({seconds:.0f}s) {script.title}")
    return 0 if made == args.count else 1


def cmd_plan(args):
    cfg = load_cfg(args.config)
    rewards = planner.rewards_by_format(load_history(), planner.load_views(args.analytics))
    print(f"{'format':24} {'n':>4} {'median views':>14}")
    for fid, n, med in planner.report(cfg["formats"], rewards):
        print(f"{fid:24} {n:4d} {med if med is None else round(med):>14}")
    counts = {}
    rng = random.Random(0)
    for _ in range(1000):
        f = planner.choose(cfg["formats"], rewards, rng)["id"]
        counts[f] = counts.get(f, 0) + 1
    print("next-upload share:", ", ".join(f"{k} {v / 10:.0f}%" for k, v in sorted(counts.items(), key=lambda x: -x[1])))
    return 0


def cmd_forecast(args):
    a = revenue.Assumptions(start=date.fromisoformat(args.start) if args.start else date.today())
    for kv in args.set or []:
        k, v = kv.split("=", 1)
        setattr(a, k, type(getattr(a, k))(v))
    print(revenue.format_report(a))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="factory")
    sub = p.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("make", help="write, check and render Shorts into outbox/")
    m.add_argument("--config", default=str(ROOT / "config.json"))
    m.add_argument("--count", type=int, default=1)
    m.add_argument("--analytics", help="YouTube Studio CSV export to steer format choice")
    m.add_argument("--dry-run", action="store_true", help="use a built-in sample script instead of calling Claude")
    m.set_defaults(fn=cmd_make)
    pl = sub.add_parser("plan", help="rank formats from analytics")
    pl.add_argument("--config", default=str(ROOT / "config.json"))
    pl.add_argument("--analytics", required=True)
    pl.set_defaults(fn=cmd_plan)
    f = sub.add_parser("forecast", help="project revenue over a year")
    f.add_argument("--start")
    f.add_argument("--set", action="append", metavar="FIELD=VALUE")
    f.set_defaults(fn=cmd_forecast)
    args = p.parse_args(argv)
    return args.fn(args)
