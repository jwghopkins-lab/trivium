#!/usr/bin/env python3
"""Unpack staged day-bundles up to London-today into the live site tree.

staging/<date>.bundle is base64 of {"menu": str, "pars": str,
"puzzles": {filename: str}} — file contents verbatim, so unpacking is
byte-identical to what deploy_pages.py would have copied. Bundles are only
casual-proofing (base64, same bar as the puzzles' own sol_obf): a public repo
cannot hold a secret from a determined reader, and the audience is friends.

Prints the released dates comma-separated on the last line (empty if none),
which the release workflow captures as its output.
"""
import base64, json, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def london_today():
    return subprocess.run(["date", "+%Y-%m-%d"], capture_output=True, text=True,
                          env={"TZ": "Europe/London"}).stdout.strip()


def main():
    today = sys.argv[1] if len(sys.argv) > 1 else london_today()
    released = []
    staging = ROOT / "staging"
    for b in sorted(staging.glob("*.bundle")) if staging.is_dir() else []:
        day = b.stem
        if day > today:
            continue
        data = json.loads(base64.b64decode(b.read_text()))
        (ROOT / "menu").mkdir(exist_ok=True)
        (ROOT / "pars").mkdir(exist_ok=True)
        (ROOT / "menu" / f"{day}.json").write_text(data["menu"])
        (ROOT / "pars" / f"{day}.json").write_text(data["pars"])
        pdir = ROOT / "puzzles" / day
        pdir.mkdir(parents=True, exist_ok=True)
        for name, content in data["puzzles"].items():
            if "/" in name or name.startswith("."):   # bundle paths stay flat
                raise SystemExit(f"suspicious puzzle filename in bundle: {name}")
            (pdir / name).write_text(content)
        b.unlink()
        released.append(day)
    print(f"today (Europe/London) = {today}", file=sys.stderr)
    print(",".join(released))


if __name__ == "__main__":
    main()
