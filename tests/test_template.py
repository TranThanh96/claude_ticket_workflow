"""End-to-end tests for the ticket-workflow template: installer, tasks_status.

Run from the repo root:  python3 -m unittest discover -s tests -v
Stdlib only. Each test builds a throwaway git repo and installs the template with the
real install.sh. This tier doesn't require the memory bank to be present to install
(a warning is printed if it's missing), so tests don't bother installing it either,
except where a test specifically wants to check the AGENTS.md merge-vs-overwrite path.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent.parent


class Project:
    """A temp git repo with the template installed."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.env = {**os.environ, "CLAUDE_PROJECT_DIR": str(root)}

    def sh(self, *cmd: str, check: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run(cmd, cwd=self.root, env=self.env, capture_output=True, text=True, check=check)

    def git(self, *args: str) -> str:
        return self.sh("git", *args).stdout.strip()

    def write(self, rel: str, text: str) -> Path:
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        return p

    def commit(self, msg: str = "wip") -> None:
        self.git("add", "-A")
        self.git("commit", "-qm", msg)

    def status(self, *args: str) -> subprocess.CompletedProcess:
        return self.sh("python3", "scripts/tasks_status.py", *args, check=False)

    def exchange_status(self, *args: str) -> subprocess.CompletedProcess:
        return self.sh("python3", "scripts/exchange_status.py", *args, check=False)


class TemplateTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = Path(tempfile.mkdtemp(prefix="ctw-test-"))
        root = self._tmp / "proj"
        root.mkdir()
        self.p = Project(root)
        self.p.git("init", "-q", "-b", "main")
        self.p.git("config", "user.email", "t@example.com")
        self.p.git("config", "user.name", "test")
        self.p.env["INIT_TICKET_WORKFLOW_TEMPLATE"] = str(TEMPLATE)
        # tasks_status.py needs to be present regardless of whether the caller wants
        # the full install-flow tested; run the installer for every test.
        self.install = self.p.sh("bash", str(TEMPLATE / "install.sh"), str(root), check=False)
        self.assertEqual(self.install.returncode, 0, self.install.stderr)
        self.p.write("app.py", "print('hi')\n")
        self.p.commit("init")

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def write_ticket(self, feature: str, ticket_id: str, **fields) -> None:
        fm = {"id": ticket_id, "title": "Do the thing", "status": "ready",
              "depends_on": "[]", "assigned_to": "null", "complexity": "small", **fields}
        body = "---\n" + "\n".join(f"{k}: {v}" for k, v in fm.items()) + "\n---\nbody\n"
        self.p.write(f".claude/tasks/{feature}/{ticket_id}-ticket.md", body)

    def write_exchange(self, feature: str, ticket_slug: str, **fields) -> None:
        data = {"ticket_path": f".claude/tasks/{feature}/{ticket_slug}.md", "stage": "plan",
                 "plan_round": 1, "turn": "delegate", "outcome": None, "skeleton_paths": [],
                 "test_paths": [], "approved_plan": None, "request": {}, "response": None,
                 "history": [], "updated_at": "2026-01-01T00:00:00Z", **fields}
        self.p.write(f".claude/tasks/{feature}/{ticket_slug}.exchange.json", json.dumps(data))


class TestInstaller(TemplateTestCase):
    def test_fresh_install_creates_workflow_files(self):
        for rel in ("AGENTS.md", ".claude/rules/workflow.md", ".claude/routing.example.json",
                    "scripts/tasks_status.py", "scripts/exchange_status.py", "scripts/_table.py",
                    ".agents/skills/exchange-check.md", ".claude/skills/to-tickets/SKILL.md",
                    ".claude/skills/implementation/SKILL.md", ".claude/skills/ticket-review/SKILL.md"):
            self.assertTrue((self.p.root / rel).is_file(), rel)

    def test_warns_when_memory_bank_is_missing(self):
        self.assertIn("no .claude/memory/ found", self.install.stderr)

    def test_no_warning_when_memory_bank_is_present(self):
        target = self._tmp / "with-bank"
        target.mkdir()
        (target / ".claude" / "memory").mkdir(parents=True)
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=target, check=True)
        res = subprocess.run(["bash", str(TEMPLATE / "install.sh"), str(target)],
                             env=self.p.env, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertNotIn("no .claude/memory/ found", res.stderr)

    def test_existing_agents_md_is_staged_not_overwritten(self):
        target = self._tmp / "existing-agents"
        target.mkdir()
        (target / "AGENTS.md").write_text("# my agents file\n")
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=target, check=True)
        res = subprocess.run(["bash", str(TEMPLATE / "install.sh"), str(target)],
                             env=self.p.env, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual((target / "AGENTS.md").read_text(), "# my agents file\n")
        self.assertTrue((target / "AGENTS.md.template").is_file())


class TestUpgrade(TemplateTestCase):
    SKILL = ".claude/skills/to-tickets/SKILL.md"

    def run_installer(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["bash", str(TEMPLATE / "install.sh"), *args, str(self.p.root)],
                              env=self.p.env, capture_output=True, text=True)

    def test_upgrade_replaces_committed_template_files(self):
        self.p.write(self.SKILL, "# old version\n")
        self.p.commit("old skill")
        res = self.run_installer("--upgrade")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn(f"^ {self.SKILL}", res.stdout)
        self.assertEqual((self.p.root / self.SKILL).read_text(), (TEMPLATE / self.SKILL).read_text())

    def test_upgrade_keeps_files_with_uncommitted_changes(self):
        self.p.write(self.SKILL, "# old version\n")
        self.p.commit("old skill")
        self.p.write(self.SKILL, "# my local edit\n")
        res = self.run_installer("--upgrade")
        self.assertIn(f"! {self.SKILL}", res.stdout)
        self.assertEqual((self.p.root / self.SKILL).read_text(), "# my local edit\n")


class TestTasksStatus(TemplateTestCase):
    def status(self, *args: str) -> subprocess.CompletedProcess:
        return self.p.status(*args)

    def test_silent_without_tasks_dir(self):
        res = self.status()
        self.assertEqual(res.returncode, 0)
        self.assertIn("not found", res.stdout)

    def test_lists_tickets_and_filters_by_status(self):
        self.write_ticket("demo", "01", status="done")
        self.write_ticket("demo", "02", status="ready", depends_on="[01]")
        out = self.status().stdout
        self.assertIn("01", out)
        self.assertIn("02", out)
        ready_only = self.status("--status", "ready").stdout
        self.assertIn("02", ready_only)
        self.assertNotIn("done", ready_only)

    def test_filters_by_feature(self):
        self.write_ticket("demo-a", "01")
        self.write_ticket("demo-b", "01")
        out = self.status("--feature", "demo-a").stdout
        self.assertIn("demo-a", out)
        self.assertNotIn("demo-b", out)

    def test_dangling_depends_on_is_an_error(self):
        self.write_ticket("demo", "01", depends_on="[99]")
        res = self.status()
        self.assertEqual(res.returncode, 1)
        self.assertIn("depends_on '99' does not match any ticket", res.stdout)

    def test_archived_and_spec_files_are_ignored(self):
        self.write_ticket("demo", "01")
        self.p.write(".claude/tasks/demo/SPEC.md", "# Spec\n")
        self.p.write(".claude/tasks/_archive/old-feature/01-ticket.md",
                     "---\nid: 01\ntitle: old\nstatus: done\n---\n")
        out = self.status().stdout
        self.assertIn("demo", out)
        self.assertNotIn("old-feature", out)


class TestExchangeStatus(TemplateTestCase):
    def status(self, *args: str) -> subprocess.CompletedProcess:
        return self.p.exchange_status(*args)

    def test_silent_without_tasks_dir(self):
        res = self.status()
        self.assertEqual(res.returncode, 0)
        self.assertIn("no exchange files found", res.stdout)

    def test_lists_and_filters_by_turn(self):
        self.write_exchange("demo", "01-ticket", turn="delegate")
        self.write_exchange("demo", "02-ticket", turn="claude")
        out = self.status().stdout
        self.assertIn("01-ticket", out)
        self.assertIn("02-ticket", out)
        delegate_only = self.status("--turn", "delegate").stdout
        self.assertIn("01-ticket", delegate_only)
        self.assertNotIn("02-ticket", delegate_only)

    def test_filters_by_feature(self):
        self.write_exchange("demo-a", "01-ticket")
        self.write_exchange("demo-b", "01-ticket")
        out = self.status("--feature", "demo-a").stdout
        self.assertIn("demo-a", out)
        self.assertNotIn("demo-b", out)

    def test_duplicate_turn_is_an_error(self):
        self.write_exchange("demo", "01-ticket", turn="delegate")
        self.write_exchange("demo", "02-ticket", turn="delegate")
        res = self.status("--turn", "delegate")
        self.assertEqual(res.returncode, 1)
        self.assertIn("more than one exchange file has turn", res.stdout)

    def test_paths_only_prints_bare_path(self):
        self.write_exchange("demo", "01-ticket", turn="delegate")
        out = self.status("--turn", "delegate", "--paths-only").stdout.strip()
        self.assertEqual(out, ".claude/tasks/demo/01-ticket.exchange.json")

    def test_filter_with_no_match_says_so_distinctly(self):
        self.write_exchange("demo", "01-ticket", turn="claude")
        out = self.status("--turn", "delegate").stdout
        self.assertIn("no exchange files match this filter", out)
        self.assertNotIn("no exchange files found.", out)

    def test_malformed_json_is_an_error(self):
        self.p.write(".claude/tasks/demo/01-ticket.exchange.json", "{not json")
        res = self.status()
        self.assertEqual(res.returncode, 1)
        self.assertIn("failed to parse as JSON", res.stdout)

    def test_archived_files_are_ignored(self):
        self.write_exchange("demo", "01-ticket")
        self.p.write(".claude/tasks/_archive/old-feature/01-ticket.exchange.json",
                     json.dumps({"turn": "delegate"}))
        out = self.status().stdout
        self.assertIn("demo", out)
        self.assertNotIn("old-feature", out)


if __name__ == "__main__":
    unittest.main()
