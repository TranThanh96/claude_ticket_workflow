#!/usr/bin/env python3
"""Shared table printer for tasks_status.py and exchange_status.py.

Not a standalone tool — imported by the two status scripts, which each build their own
rows and handle their own "nothing to show" message before calling this.
"""
from __future__ import annotations


def print_rows(rows: list[list[str]]) -> None:
    """Print `rows` (first row is the header) as padded columns with a dashed
    separator after the header."""
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    for i, row in enumerate(rows):
        print("  ".join(cell.ljust(widths[j]) for j, cell in enumerate(row)))
        if i == 0:
            print("  ".join("-" * w for w in widths))
