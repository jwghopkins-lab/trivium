#!/usr/bin/env python3
"""Is today's puzzle actually being SERVED — not merely committed?

On 21 Aug the repo had the day, the release run was green, the deploy job was
green, and the site did not have the puzzle: the deploy had checked out the
commit that triggered the run rather than the branch tip the run had just
pushed. Every repo-side check passed because every repo-side check was true.
The only test that catches that class is fetching the live CDN and looking.

Runs in Actions (this sandboxed dev environment cannot reach github.io).
Retries briefly because a Pages deploy takes a few seconds to propagate.

Usage: check_live.py [YYYY-MM-DD]   (default: today in London)
Exit 0 when the served menu for the day parses and matches the date;
1 otherwise, with the reason on stdout.
"""
import json, subprocess, sys, time, urllib.request

SITE = "https://jwghopkins-lab.github.io/trivium"
TRIES, GAP = 8, 15          # up to two minutes of propagation grace


def london_today():
    return subprocess.run(["date", "+%Y-%m-%d"], capture_output=True, text=True,
                          env={"TZ": "Europe/London"}).stdout.strip()


def main():
    day = sys.argv[1] if len(sys.argv) > 1 else london_today()
    url = f"{SITE}/menu/{day}.json"
    last = ""
    for i in range(TRIES):
        try:
            with urllib.request.urlopen(url, timeout=20) as r:
                menu = json.loads(r.read().decode())
            if menu.get("date") == day and menu.get("tiers"):
                topics = sorted(t["id"] for tl in menu["tiers"].values() for t in tl)
                print(f"LIVE {day}: {' '.join(topics)}")
                return 0
            last = f"served menu parses but is for {menu.get('date')!r}"
        except Exception as e:
            last = str(e)
        if i < TRIES - 1:
            time.sleep(GAP)
    print(f"::error::{url} is not serving {day}'s menu ({last}) — the site is "
          f"stale even if the repo is right; redeploy Pages from the main tip")
    return 1


if __name__ == "__main__":
    sys.exit(main())
