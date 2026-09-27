#!/usr/bin/env python3
"""List ticket status across .claude/tasks/ without opening every ticket file.

  python3 scripts/tasks_status.py                    # every ticket, every feature
  python3 scripts/tasks_status.py --status ready      # only tickets with no blocker left
  python3 scripts/tasks_status.py --feature user-auth # only one feature folder

Also validates that every `depends_on` id resolves to a real ticket in the same
feature folder; a dangling id is printed as an ERROR and the exit code is 1.

Stdlib only: tickets carry a small flat frontmatter (`key: value`, `key: [a, b]`
lists), not full YAML, so no PyYAML dependency is needed to read it.
"""
from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TASKS = ROOT / ".claude" / "tasks"
FIELDS = ("id", "title", "status", "depends_on", "assigned_to", "complexity")


def parse_frontmatter(text: str) -> dict[str, str | list[str]]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    data: dict[str, str | list[str]] = {}
    for line in text[4:end].splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if value.startswith("[") and value.endswith("]"):
            data[key] = [v.strip().strip("\"'") for v in value[1:-1].split(",") if v.strip()]
        else:
            data[key] = value.strip("\"'")
    return data


def find_tickets(tasks_dir: Path) -> list[Path]:
    if not tasks_dir.is_dir():
        return []
    return [
        p for p in sorted(tasks_dir.rglob("*.md"))
        if "_archive" not in p.relative_to(tasks_dir).parts and p.name != "SPEC.md"
    ]


def load_tickets(tasks_dir: Path) -> list[dict]:
    tickets = []
    for path in find_tickets(tasks_dir):
        fm = parse_frontmatter(path.read_text(encoding="utf-8"))
        ticket = {field: fm.get(field, "") for field in FIELDS}
        ticket["feature"] = path.relative_to(tasks_dir).parts[0]
        ticket["path"] = path.relative_to(ROOT).as_posix()
        tickets.append(ticket)
    return tickets


def check_dangling_deps(tickets: list[dict]) -> list[str]:
    known = {(t["feature"], t["id"]) for t in tickets if t["id"]}
    errors = []
    for t in tickets:
        for dep in t["depends_on"] or []:
            if (t["feature"], dep) not in known:
                errors.append(f"{t['path']}: depends_on '{dep}' does not match any ticket in "
                              f"feature '{t['feature']}'.")
    return errors


def print_table(tickets: list[dict]) -> None:
    if not tickets:
        print("tasks-status: no tickets found.")
        return
    rows = [["feature", "id", "title", "status", "depends_on", "assigned_to", "complexity"]]
    for t in tickets:
        rows.append([
            t["feature"], t["id"], t["title"], t["status"],
            ",".join(t["depends_on"]) or "-", t["assigned_to"] or "-", t["complexity"] or "-",
        ])
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    for i, row in enumerate(rows):
        print("  ".join(cell.ljust(widths[j]) for j, cell in enumerate(row)))
        if i == 0:
            print("  ".join("-" * w for w in widths))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--status", help="only tickets with this status")
    ap.add_argument("--feature", help="only this feature-slug folder")
    args = ap.parse_args()

    if not TASKS.is_dir():
        print(f"tasks-status: {TASKS.relative_to(ROOT)} not found; nothing to check.")
        return 0

    tickets = load_tickets(TASKS)
    errors = check_dangling_deps(tickets)

    shown = tickets
    if args.status:
        shown = [t for t in shown if t["status"] == args.status]
    if args.feature:
        shown = [t for t in shown if t["feature"] == args.feature]
    print_table(shown)

    for msg in errors:
        print(f"ERROR  {msg}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
