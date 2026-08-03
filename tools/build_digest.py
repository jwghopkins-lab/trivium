#!/usr/bin/env python3
"""Build the daily TRIVIUM digest page from the public results feed.

Runs in GitHub Actions (the only place with network access to Supabase and a
schedule that does not depend on anyone's session being awake). Reads the same
anon-readable data the app itself shows, so it exposes nothing new.

Usage: build_digest.py <results.json> <pars_dir> <day> <out.html>
"""
import html
import json
import statistics
import sys
from collections import defaultdict
from datetime import date, timedelta


def dayshift(d, n):
    y, m, dd = map(int, d.split("-"))
    return (date(y, m, dd) + timedelta(days=n)).isoformat()


def fmt(s):
    s = int(s)
    return f"{s // 60}:{s % 60:02d}"


def short(combo):
    return "·".join("".join(p[0].upper() for p in t.split("-")) for t in combo.split("|") if t)


def main():
    results_path, pars_dir, day, out_path = sys.argv[1:5]
    rows = json.load(open(results_path))
    rows = [r for r in rows if r.get("player_name") != "CITest"]
    try:
        pars = json.load(open(f"{pars_dir}/{day}.json"))
    except Exception:
        pars = {}
    par_vals = sorted(pars.values()) if pars else []
    par_mid = par_vals[len(par_vals) // 2] if par_vals else 300
    par_of = lambda ck: float(pars.get(ck) or par_mid)

    today = [r for r in rows if r["day"] == day]
    ranked = sorted([r for r in today if not r.get("assisted")], key=lambda r: r["seconds"])
    assisted = [r for r in today if r.get("assisted")]

    # per-player history for streaks, averages and personal bests
    by_name = defaultdict(list)
    for r in rows:
        by_name[r["player_name"]].append(r)
    stats = {}
    for name, rs in by_name.items():
        days = {r["day"] for r in rs}
        streak, d = 0, day
        while d in days:
            streak += 1
            d = dayshift(d, -1)
        prior = [r["seconds"] for r in rs
                 if r["day"] < day and not r.get("assisted")]
        stats[name] = {
            "streak": streak,
            "prior_avg": statistics.mean(prior) if prior else None,
            "prior_best": min(prior) if prior else None,
            "played": len(rs),
        }

    # ---- awards -----------------------------------------------------------
    awards = []
    if ranked:
        w = ranked[0]
        awards.append(("🏆", "Fastest solve",
                       f"{w['player_name']} — {fmt(w['seconds'])}"
                       + (f" with {w['hints']} hint{'s' if w['hints'] != 1 else ''}" if w.get("hints") else " clean")))

    # best performance relative to that puzzle's par (fair across combos)
    if ranked:
        vs_par = min(ranked, key=lambda r: r["seconds"] / par_of(r["combo_key"]))
        ratio = vs_par["seconds"] / par_of(vs_par["combo_key"])
        awards.append(("🎯", "Best against par",
                       f"{vs_par['player_name']} — {int(round((1 - ratio) * 100))}% under par on {short(vs_par['combo_key'])}"))

    pbs = [(r, stats[r["player_name"]]["prior_best"]) for r in ranked
           if stats[r["player_name"]]["prior_best"] and r["seconds"] < stats[r["player_name"]]["prior_best"]]
    for r, old in sorted(pbs, key=lambda x: x[0]["seconds"] - x[1])[:2]:
        awards.append(("⚡", "Personal best",
                       f"{r['player_name']} — {fmt(r['seconds'])}, beating {fmt(old)}"))

    streakers = sorted([(s["streak"], n) for n, s in stats.items() if s["streak"] >= 2], reverse=True)
    if streakers:
        n_max = streakers[0][0]
        names = [n for s, n in streakers if s == n_max]
        awards.append(("🔥", "Longest streak",
                       f"{', '.join(names)} — {n_max} days running"))

    goblins = [r for r in today if (r.get("hints") or 0) >= 3]
    if goblins:
        awards.append(("💡", "Hint Goblin",
                       ", ".join(sorted({r["player_name"] for r in goblins}))
                       + " — maxed out the hints"))

    if len(ranked) > 1:
        slow = ranked[-1]
        awards.append(("🐌", "Scenic route",
                       f"{slow['player_name']} — {fmt(slow['seconds'])}, savouring every clue"))

    # ---- physics check (playful, evidence-based, never an accusation) ------
    flags = []
    for r in ranked:
        ratio = r["seconds"] / par_of(r["combo_key"])
        own = [x["seconds"] for x in by_name[r["player_name"]]
               if x["day"] != day and not x.get("assisted")]
        own_med = statistics.median(own) if own else None
        reasons = []
        if ratio < 0.45:
            reasons.append(f"{int(round(ratio * 100))}% of par")
        if own_med and r["seconds"] * 2.5 < own_med:
            reasons.append(f"{own_med / r['seconds']:.1f}× their own usual pace")
        secs_per_word = r["seconds"] / 12.0
        if secs_per_word < 8:
            reasons.append(f"~{secs_per_word:.0f}s per word including reading it")
        if len(reasons) >= 2:
            flags.append((r, reasons))

    # ---- share text -------------------------------------------------------
    lines = [f"TRIVIUM 🧩 {day}", ""]
    for i, r in enumerate(ranked[:5], 1):
        medal = ["🥇", "🥈", "🥉"][i - 1] if i <= 3 else f"{i}."
        s = stats[r["player_name"]]["streak"]
        lines.append(f"{medal} {r['player_name']} {fmt(r['seconds'])}"
                     + (f" 💡{r['hints']}" if r.get("hints") else "")
                     + (f" 🔥{s}" if s > 1 else ""))
    if len(ranked) > 5:
        lines.append(f"…and {len(ranked) - 5} more")
    lines.append("")
    for icon, title, text in awards[:4]:
        lines.append(f"{icon} {title}: {text}")
    share = "\n".join(lines)

    # ---- page -------------------------------------------------------------
    def row_html(r, rank):
        s = stats[r["player_name"]]
        medal = ["🥇", "🥈", "🥉"][rank - 1] if rank and rank <= 3 else (f"{rank}." if rank else "–")
        sub = f"{short(r['combo_key'])}"
        if s["prior_avg"]:
            delta = r["seconds"] - s["prior_avg"]
            sub += f" · {'−' if delta < 0 else '+'}{fmt(abs(delta))} vs their average"
        return (f"<tr><td class=r>{medal}</td>"
                f"<td><b>{html.escape(r['player_name'])}</b>"
                + (f" <span class=st>🔥{s['streak']}</span>" if s["streak"] > 1 else "")
                + f"<div class=sub>{html.escape(sub)}</div></td>"
                f"<td class=t>{fmt(r['seconds'])}"
                + (f"<div class=sub>💡{r['hints']}</div>" if r.get("hints") else "")
                + "</td></tr>")

    board = "".join(row_html(r, i) for i, r in enumerate(ranked, 1))
    board += "".join(row_html(r, None) for r in assisted)
    award_html = "".join(
        f"<div class=aw><span class=ic>{i}</span><div><b>{html.escape(t)}</b>"
        f"<div class=sub>{html.escape(x)}</div></div></div>" for i, t, x in awards)
    flag_html = ""
    for r, reasons in flags:
        flag_html += (f"<div class=aw><span class=ic>🚩</span><div>"
                      f"<b>Physics-defying solve: {html.escape(r['player_name'])}</b>"
                      f"<div class=sub>{html.escape(fmt(r['seconds']))} — "
                      + html.escape("; ".join(reasons))
                      + ". Suspiciously brilliant, or a second run at the same grid?</div></div></div>")

    played = len({r["player_name"] for r in today})
    total = len({r["player_name"] for r in rows})
    page = f"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>TRIVIUM — {day}</title><style>
:root{{--bg:#F3F5F1;--card:#fff;--ink:#1C2227;--soft:#5A6570;--line:#C9CFC9;--acc:#2B52D8}}
@media(prefers-color-scheme:dark){{:root{{--bg:#14181C;--card:#1D2329;--ink:#E7EBEE;--soft:#93A0AB;--line:#39424A;--acc:#6E8EF5}}}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;
padding:16px;display:flex;justify-content:center}}
.wrap{{width:100%;max-width:560px}}
h1{{font-family:Georgia,serif;font-size:1.6rem;letter-spacing:.03em}}
h1 span{{color:var(--acc)}}
.date{{color:var(--soft);font-size:.8rem;text-transform:uppercase;letter-spacing:.08em;margin-bottom:14px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px;margin-bottom:12px}}
h2{{font-size:.72rem;text-transform:uppercase;letter-spacing:.09em;color:var(--soft);margin-bottom:10px}}
table{{width:100%;border-collapse:collapse}}
td{{padding:6px 0;vertical-align:top;border-bottom:1px solid var(--line)}}
tr:last-child td{{border-bottom:none}}
td.r{{width:2.2em;color:var(--soft)}}
td.t{{text-align:right;font-family:ui-monospace,Menlo,monospace;font-variant-numeric:tabular-nums;white-space:nowrap}}
.sub{{font-size:.72rem;color:var(--soft)}}
.st{{font-size:.75rem}}
.aw{{display:flex;gap:10px;padding:7px 0;align-items:flex-start}}
.aw+.aw{{border-top:1px solid var(--line)}}
.ic{{font-size:1.15rem;line-height:1.2}}
button{{width:100%;padding:12px;border:none;border-radius:10px;background:var(--acc);color:#fff;
font-size:.95rem;font-weight:600;cursor:pointer}}
pre{{white-space:pre-wrap;font:13px/1.45 ui-monospace,Menlo,monospace;color:var(--soft);
background:var(--bg);border-radius:8px;padding:10px;margin-bottom:10px;overflow-x:auto}}
.foot{{color:var(--soft);font-size:.7rem;text-align:center;margin-top:14px;line-height:1.5}}
</style></head><body><div class=wrap>
<h1>TRIVI<span>UM</span></h1>
<div class=date>Daily digest · {day}</div>
<div class=card><h2>Today's board — {played} played{f' of {total} all-time' if total > played else ''}</h2>
<table>{board or '<tr><td class=sub>Nobody has posted a time yet today.</td></tr>'}</table></div>
{f'<div class=card><h2>Honours</h2>{award_html}</div>' if award_html else ''}
{f'<div class=card><h2>Steward&#39;s enquiry</h2>{flag_html}</div>' if flag_html else ''}
<div class=card><h2>Share it</h2><pre id=share>{html.escape(share)}</pre>
<button onclick="navigator.clipboard.writeText(document.getElementById('share').textContent).then(()=>{{this.textContent='Copied!';setTimeout(()=>this.textContent='Copy for WhatsApp',1600)}})">Copy for WhatsApp</button></div>
<div class=foot>Times are self-reported by the app. Ranked solves exclude assisted ones.<br>
Built automatically each evening · <a href="./" style="color:var(--acc)">play today's puzzle</a></div>
</div></body></html>"""

    open(out_path, "w").write(page)
    print(f"digest for {day}: {len(ranked)} ranked, {len(assisted)} assisted, "
          f"{len(awards)} awards, {len(flags)} flagged -> {out_path}")


if __name__ == "__main__":
    main()
