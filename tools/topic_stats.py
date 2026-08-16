#!/usr/bin/env python3
"""Which topics do players actually choose? Reads a results dump and ranks them.

Run from .github/workflows/stats.yml, which curls results with the public anon
key (results is the one table anon may read). The dev sandbox cannot reach
Supabase at all — the agent proxy refuses the CONNECT — so Actions is the only
route from a Claude session to play data, and printing to the job log is what
makes it readable afterwards.

A result row carries combo_key, "a|b|c": the three topic ids that were played,
sorted. Picks are not independent — a topic can only be chosen on the days it
was on the menu — so a raw count rewards being offered often. Both are printed:
the raw count, and picks per day offered, which is the honest popularity signal.

Usage: topic_stats.py <results.json> [menu_dir]
"""
import json, sys, collections
from pathlib import Path


def main():
    rows = json.loads(Path(sys.argv[1]).read_text())
    menu_dir = Path(sys.argv[2] if len(sys.argv) > 2 else "menu")

    offered = collections.Counter()
    days_live = 0
    for f in sorted(menu_dir.glob("*.json")):
        days_live += 1
        for tier, entries in json.loads(f.read_text())["tiers"].items():
            for e in entries:
                offered[e["id"]] += 1

    on_menu = collections.defaultdict(set)          # topic -> days it was offered
    for f in sorted(menu_dir.glob("*.json")):
        doc = json.loads(f.read_text())
        for tier, entries in doc["tiers"].items():
            for e in entries:
                on_menu[e["id"]].add(doc["date"])

    picks, players, by_day = collections.Counter(), collections.defaultdict(set), collections.Counter()
    for r in rows:
        combo = r.get("combo_key") or ""
        if not combo:
            continue
        by_day[r.get("day", "?")] += 1
        for tid in combo.split("|"):
            picks[tid] += 1
            players[tid].add(r.get("player_name", ""))

    # The honest metric. Every play picks exactly one topic per shelf, so a
    # topic's share of the plays on the days it was offered is its head-to-head
    # win rate against the other two on its shelf: 33% is average, and it is not
    # inflated by having been offered on a busy day the way a raw count is.
    def share(tid):
        seen = sum(n for day, n in by_day.items() if day in on_menu.get(tid, ()))
        return (picks[tid] / seen) if seen else 0.0

    print(f"{len(rows)} completed puzzles across {len(by_day)} days, "
          f"{days_live} days published\n")
    print("plays per day:")
    for day, n in sorted(by_day.items()):
        print(f"  {day}  {n:>3}  {'#' * n}")

    print(f"\nshare = % of players who chose it on the days it was offered "
          f"(33% is average for a shelf of three)\n")
    print(f"{'topic':<24}{'picks':>6}{'days':>6}{'share':>8}{'players':>9}")
    rank = sorted(set(offered) | set(picks), key=lambda t: -share(t))
    for tid in rank:
        print(f"{tid:<24}{picks[tid]:>6}{offered.get(tid, 0):>6}"
              f"{share(tid) * 100:>7.0f}%{len(players[tid]):>9}")

    never = sorted(set(offered) - set(picks))
    if never:
        print(f"\noffered but never picked ({len(never)}): {', '.join(never)}")


if __name__ == "__main__":
    main()
