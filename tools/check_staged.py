#!/usr/bin/env python3
"""Is tomorrow's puzzle actually ready to publish? Run hours before it is due.

The release job at ~00:05 London can only publish what is already sitting in
staging/. Everything upstream of that — authoring the words, baking the 27
grids, bundling them here — happens in Claude sessions that have failed
silently more than once. This check runs in the evening, while there is still
time to do something about it, and fails the workflow when tomorrow is not
ready: a red run is a notification, whereas an unbaked day discovers itself at
midnight when nobody is awake.

Checks tomorrow strictly (missing or malformed = failure) and reports the days
after it as runway, since a thin runway is a warning rather than an emergency.

Usage: check_staged.py [YYYY-MM-DD as "today"]   (default: today in London)
"""
import base64, json, subprocess, sys, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXPECTED_PUZZLES = 27          # 3 topics per shelf, every combination
RUNWAY_TARGET = 3


def london_today():
    return subprocess.run(["date", "+%Y-%m-%d"], capture_output=True, text=True,
                          env={"TZ": "Europe/London"}).stdout.strip()


def shift(day, n):
    d = datetime.date.fromisoformat(day) + datetime.timedelta(days=n)
    return d.isoformat()


def inspect(day):
    """None if the day is not ready, else a one-line description of what is."""
    live = ROOT / "menu" / f"{day}.json"
    if live.exists():
        return "already live"
    b = ROOT / "staging" / f"{day}.bundle"
    if not b.exists():
        return None
    try:
        data = json.loads(base64.b64decode(b.read_text()))
        n = len(data["puzzles"])
        if not data.get("menu") or not data.get("pars") or n != EXPECTED_PUZZLES:
            print(f"::error::{day}: bundle is malformed — {n} puzzles, "
                  f"menu={'yes' if data.get('menu') else 'NO'}, "
                  f"pars={'yes' if data.get('pars') else 'NO'}")
            return None
        return f"staged, {n} puzzles"
    except Exception as e:                        # truncated, not base64, bad json
        print(f"::error::{day}: bundle unreadable — {type(e).__name__}: {e}")
        return None


def main():
    today = sys.argv[1] if len(sys.argv) > 1 else london_today()
    tomorrow = shift(today, 1)
    print(f"today is {today} (Europe/London); checking {tomorrow} and the runway behind it\n")

    ready = inspect(tomorrow)
    print(f"  {tomorrow}  {ready or 'NOT READY'}   <- publishes tonight")
    later = []
    for i in range(2, RUNWAY_TARGET + 1):
        day = shift(today, i)
        state = inspect(day)
        print(f"  {day}  {state or 'not staged'}")
        if state:
            later.append(day)

    if not ready:
        print(f"\n::error::{tomorrow} is not ready to publish and it is due tonight. "
              f"Bake and stage it: pipeline/bake_day.py {tomorrow} --attempts 150 "
              f"--ease 0.1, then pipeline/stage_days.py, then push the trivium repo.")
        return 1
    if len(later) + 1 < RUNWAY_TARGET:
        # Not a failure: tonight is safe, and there is a day to fix it in.
        print(f"\n::warning::only {len(later) + 1} of {RUNWAY_TARGET} days are ready. "
              f"Tonight publishes, but the runway is thin.")
    print("\ntomorrow is ready")
    return 0


if __name__ == "__main__":
    sys.exit(main())
