#!/usr/bin/env python3
"""Flatten what was actually published into a queryable log: which topics were
offered each day, and which answers each puzzle used.

The repo already holds this information, but in two shapes that are awkward to
ask questions of: app/menu/<day>.json (the nine topics offered) and
app/puzzles/<day>/<combo>.json (the grids). This turns both into flat rows, so
"when did ORCA last appear, and how often?" is one GROUP BY rather than a walk
over 300 files.

Answers are re-derived from each puzzle's shipped solution rather than taken
from history.json — same principle as verify_bakes.py: read the artifact, not
the builder's account of it. That way the log records what players were served.

RELEASE GATE: only days up to --through (default today, Europe/London) are
exported. Future days are baked days ahead, and their answers must never leave
the repo — a readable log of unreleased solutions is a puzzle spoiler.

Usage:
  export_log.py                          # write app/sql/data/*.csv
  export_log.py --post                   # also insert into Supabase
  export_log.py --through 2026-08-06     # pin the release gate
"""
import argparse, base64, csv, json, re, sys, urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
APP = BASE
OUT = BASE / "tools" / "logdata"


def london_today():
    # BST from the last Sunday of March to the last Sunday of October; for a
    # date stamp an hour either way never changes the answer except in the small
    # hours, and the bake runs at 00:20 UTC when London is already on the day.
    now = datetime.now(timezone.utc)
    return (now + timedelta(hours=1)).date().isoformat() if 3 <= now.month <= 10 \
        else now.date().isoformat()


def deobfuscate(sol_obf, pid):
    raw = base64.b64decode(sol_obf)
    return "".join(chr(b ^ ord(pid[i % len(pid)])) for i, b in enumerate(raw)).split("\n")


def entry_answer(entry, grid):
    r, c, n = entry["row"], entry["col"], entry["length"]
    if entry["dir"] == "A":
        return "".join(grid[r][c + i] for i in range(n))
    return "".join(grid[r + i][c] for i in range(n))


def collect(through):
    menu_rows, puzzle_rows = [], []
    for mf in sorted((APP / "menu").glob("*.json")):
        day = mf.stem
        if day > through:
            continue
        menu = json.loads(mf.read_text())
        for tier, topics in menu["tiers"].items():
            for t in topics:
                menu_rows.append({"day": day, "tier": tier,
                                  "topic_id": t["id"], "topic_label": t["label"]})
        for pf in sorted((APP / "puzzles" / day).glob("*.json")):
            pz = json.loads(pf.read_text())
            grid = deobfuscate(pz["sol_obf"], pz["id"])
            for e in pz["entries"]:
                puzzle_rows.append({
                    "day": day, "combo_key": pz["combo_key"], "topic_id": e["topic"],
                    "tier": pz["topics"][e["topic"]]["tier"],
                    "answer": entry_answer(e, grid)})
    # a shared cell means two entries can spell the same answer only if the
    # grid is broken, but dedupe on the table's own key regardless
    seen, deduped = set(), []
    for r in puzzle_rows:
        k = (r["day"], r["combo_key"], r["answer"])
        if k not in seen:
            seen.add(k)
            deduped.append(r)
    return menu_rows, deduped


def write_csv(path, rows, cols):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


def post(table, rows, url, key):
    """Insert, ignoring rows already logged. PostgREST needs the resolution
    header AND an on_conflict target, or a re-run of a published day 409s."""
    sent = 0
    for i in range(0, len(rows), 500):
        chunk = rows[i:i + 500]
        conflict = "day,topic_id" if table == "menu_log" else "day,combo_key,answer"
        req = urllib.request.Request(
            f"{url}/rest/v1/{table}?on_conflict={conflict}",
            data=json.dumps(chunk).encode(), method="POST",
            headers={"apikey": key, "Authorization": f"Bearer {key}",
                     "Content-Type": "application/json",
                     "Prefer": "resolution=ignore-duplicates,return=minimal"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                if r.status >= 300:
                    raise SystemExit(f"{table}: HTTP {r.status}")
        except urllib.error.HTTPError as e:
            # the status alone is undiagnosable (PostgREST reuses 401 for
            # several distinct causes); the body names the actual error
            raise SystemExit(f"{table}: HTTP {e.code}: {e.read().decode()[:500]}")
        sent += len(chunk)
    return sent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--through", default=None)
    ap.add_argument("--post", action="store_true")
    a = ap.parse_args()
    through = a.through or london_today()

    menu_rows, puzzle_rows = collect(through)
    write_csv(OUT / "menu_log.csv", menu_rows, ["day", "tier", "topic_id", "topic_label"])
    write_csv(OUT / "puzzle_log.csv", puzzle_rows, ["day", "combo_key", "topic_id", "tier", "answer"])
    days = sorted({r["day"] for r in menu_rows})
    print(f"released through {through}: {len(days)} days, "
          f"{len(menu_rows)} menu rows, {len(puzzle_rows)} answer rows")

    if a.post:
        cfg = (APP / "config.js").read_text()
        url = re.search(r'SUPABASE_URL:\s*"([^"]+)"', cfg).group(1)
        key = re.search(r'SUPABASE_ANON_KEY:\s*"([^"]+)"', cfg).group(1)
        if not url or "YOUR" in url:
            raise SystemExit("config.js has no real Supabase URL")
        print(f"menu_log:   {post('menu_log', menu_rows, url, key)} rows sent")
        print(f"puzzle_log: {post('puzzle_log', puzzle_rows, url, key)} rows sent")


if __name__ == "__main__":
    main()
