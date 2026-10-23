"""Pick the next format with Thompson sampling over past performance.

Reward is log(views) of each published Short, joined from a YouTube Studio
analytics CSV export by video title. Formats with little data get explored;
formats that keep winning get most of the uploads.
"""
import csv
import math
import random

TITLE_COLS = ("Video title", "동영상 제목", "title")
VIEWS_COLS = ("Views", "조회수", "views")
PRIOR_MEAN, PRIOR_N = math.log(1000), 1.0


def _col(row, names):
    for n in names:
        if n in row and row[n] not in (None, ""):
            return row[n]
    return None


def load_views(csv_path):
    views = {}
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            title, v = _col(row, TITLE_COLS), _col(row, VIEWS_COLS)
            if title and v:
                views[title.strip()] = float(str(v).replace(",", ""))
    return views


def rewards_by_format(history, views):
    out = {}
    for h in history:
        v = views.get(h["title"].strip())
        if v is not None:
            out.setdefault(h["format"], []).append(math.log1p(v))
    return out


def choose(formats, rewards, rng=random):
    best, best_draw = None, -math.inf
    for fmt in formats:
        xs = rewards.get(fmt["id"], [])
        n = PRIOR_N + len(xs)
        mean = (PRIOR_MEAN * PRIOR_N + sum(xs)) / n
        draw = rng.gauss(mean, 1.0 / math.sqrt(n))
        if draw > best_draw:
            best, best_draw = fmt, draw
    return best


def report(formats, rewards):
    rows = []
    for fmt in formats:
        xs = rewards.get(fmt["id"], [])
        median = math.expm1(sorted(xs)[len(xs) // 2]) if xs else None
        rows.append((fmt["id"], len(xs), median))
    return sorted(rows, key=lambda r: -(r[2] or 0))
