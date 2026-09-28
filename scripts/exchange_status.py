#!/usr/bin/env python3
"""Find the ticket exchange file(s) awaiting action, without hand-rolled globbing.

  python3 scripts/exchange_status.py                     # every exchange file, every feature
  python3 scripts/exchange_status.py --turn delegate       # only files the delegate CLI should act on
  python3 scripts/exchange_status.py --turn claude        # only files Claude should act on
  python3 scripts/exchange_status.py --feature user-auth  # scope to one feature folder
  python3 scripts/exchange_status.py --turn delegate --paths-only   # just the path, for scripting

Both the Main Agent (before writing turn: "delegate" for a new dispatch) and the delegate's own
exchange-check skill (to find which file to act on) call this instead of separately
reimplementing the same glob-and-filter logic.

Exit code is 1 if a file fails to parse as JSON, or if --turn is given and more than one file
matches it — under the one-ticket-active-at-a-time protocol this tier assumes, that's a bug to
investigate, never a race to resolve by picking one.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from _table import print_rows

ROOT = Path(__file__).resolve().parent.parent
TASKS = ROOT / ".claude" / "tasks"
SUFFIX = ".exchange.json"
FIELDS = ("id", "feature", "path", "stage", "turn", "outcome", "plan_round", "updated_at")


def find_exchange_files(tasks_dir: Path) -> list[Path]:
    if not tasks_dir.is_dir():
        return []
    return [
        p for p in sorted(tasks_dir.rglob(f"*{SUFFIX}"))
        if "_archive" not in p.relative_to(tasks_dir).parts
    ]


def load_exchanges(tasks_dir: Path) -> tuple[list[dict], list[str]]:
    exchanges = []
    errors = []
    for path in find_exchange_files(tasks_dir):
        rel = path.relative_to(ROOT).as_posix()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            errors.append(f"{rel}: failed to parse as JSON ({exc}).")
            continue
        ticket_slug = path.name[: -len(SUFFIX)]
        exchanges.append({
            "id": ticket_slug.split("-", 1)[0],
            "feature": path.relative_to(tasks_dir).parts[0],
            "path": rel,
            "stage": data.get("stage", ""),
            "turn": data.get("turn", ""),
            "outcome": data.get("outcome"),
            "plan_round": data.get("plan_round", ""),
            "updated_at": data.get("updated_at", ""),
        })
    return exchanges, errors


def print_table(shown: list[dict], any_exist: bool) -> None:
    """`any_exist` distinguishes "no exchange files at all" from "none matched the
    given --turn/--feature filter" — otherwise an empty --turn match looks identical
    to a genuinely empty tasks/ tree."""
    if not shown:
        if any_exist:
            print("exchange-status: no exchange files match this filter.")
        else:
            print("exchange-status: no exchange files found.")
        return
    rows = [list(FIELDS)]
    for e in shown:
        rows.append([str(e[f]) if e[f] not in (None, "") else "-" for f in FIELDS])
    print_rows(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--turn", choices=["delegate", "claude", "none"], help="only files with this turn")
    ap.add_argument("--feature", help="only this feature-slug folder")
    ap.add_argument("--paths-only", action="store_true", help="print matching paths, no table")
    args = ap.parse_args()

    exchanges, errors = load_exchanges(TASKS)

    shown = exchanges
    if args.turn:
        shown = [e for e in shown if e["turn"] == args.turn]
    if args.feature:
        shown = [e for e in shown if e["feature"] == args.feature]

    if args.paths_only:
        for e in shown:
            print(e["path"])
    else:
        print_table(shown, any_exist=bool(exchanges))

    for msg in errors:
        print(f"ERROR  {msg}")
    if args.turn and len(shown) > 1:
        print(f"ERROR  more than one exchange file has turn: \"{args.turn}\" — this should be "
              f"impossible under the one-ticket-active-at-a-time protocol; treat it as a bug, "
              f"don't pick one to act on.")
        return 1
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
