"""Day-by-day revenue projection for a Shorts channel.

Two income streams:
- Shorts ad revenue: only after joining YPP (1,000 subs + 10M Shorts views in
  90 days; 20M for applications from 2027-02-01) plus a review delay.
- Description/pinned-comment links (affiliate or own product): from day one.
All rates are inputs; defaults are conservative public estimates.
"""
from dataclasses import dataclass
from datetime import date, timedelta

RULE_CHANGE = date(2027, 2, 1)


@dataclass
class Assumptions:
    start: date
    days: int = 365
    uploads_per_day: float = 2
    views_per_short_start: float = 800
    views_growth_per_month: float = 0.25   # per-Short reach growth while the channel learns
    views_per_short_cap: float = 60000
    subs_per_1k_views: float = 1.5
    shorts_rpm_usd: float = 0.06           # creator share per 1,000 Shorts views
    link_ctr: float = 0.0015               # clicks per view on description/pinned links
    link_conversion: float = 0.03
    link_payout_usd: float = 8.0           # commission or product margin per sale
    cost_per_video_usd: float = 0.15       # API + TTS
    ypp_review_days: int = 30
    starting_subs: int = 0


def ypp_threshold(on):
    return 20_000_000 if on >= RULE_CHANGE else 10_000_000


def simulate(a: Assumptions):
    daily_views, subs = [], a.starting_subs
    joined = None
    rows = []
    for d in range(a.days):
        today = a.start + timedelta(days=d)
        per_short = min(a.views_per_short_cap, a.views_per_short_start * (1 + a.views_growth_per_month) ** (d / 30))
        views = per_short * a.uploads_per_day
        daily_views.append(views)
        subs += views / 1000 * a.subs_per_1k_views
        rolling = sum(daily_views[-90:])
        if joined is None and subs >= 1000 and rolling >= ypp_threshold(today):
            joined = today + timedelta(days=a.ypp_review_days)
        ads = views / 1000 * a.shorts_rpm_usd if joined and today >= joined else 0.0
        links = views * a.link_ctr * a.link_conversion * a.link_payout_usd
        cost = a.uploads_per_day * a.cost_per_video_usd
        rows.append({"date": today, "views": views, "subs": subs, "rolling90": rolling,
                     "ads": ads, "links": links, "cost": cost})
    return rows, joined


def monthly(rows):
    out = {}
    for r in rows:
        k = r["date"].strftime("%Y-%m")
        m = out.setdefault(k, {"views": 0, "ads": 0, "links": 0, "cost": 0, "subs": 0})
        for f in ("views", "ads", "links", "cost"):
            m[f] += r[f]
        m["subs"] = r["subs"]
    return out


def format_report(a: Assumptions):
    rows, joined = simulate(a)
    lines = [f"{'month':8} {'views':>12} {'subs':>9} {'ads$':>9} {'links$':>9} {'cost$':>8} {'net$':>9}"]
    total = 0.0
    for k, m in monthly(rows).items():
        net = m["ads"] + m["links"] - m["cost"]
        total += net
        lines.append(f"{k:8} {m['views']:12,.0f} {m['subs']:9,.0f} {m['ads']:9,.2f} {m['links']:9,.2f} {m['cost']:8,.2f} {net:9,.2f}")
    lines.append(f"YPP ad revenue starts: {joined or 'not within horizon'}")
    lines.append(f"Net over {a.days} days: ${total:,.2f}")
    ads = sum(r["ads"] for r in rows)
    links = sum(r["links"] for r in rows)
    lines.append(f"Share from links: {links / (ads + links):.0%}" if ads + links else "No revenue")
    return "\n".join(lines)
