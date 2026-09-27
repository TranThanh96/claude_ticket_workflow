#!/usr/bin/env bash
# Scaffold the claude_ticket_workflow ticket workflow into a project.
#
# Usage:
#   install.sh [--upgrade] [target_dir]
#
# Env:
#   INIT_TICKET_WORKFLOW_TEMPLATE  path to this template repo (default: the directory
#                                  this script lives in)
#
# Spec-first planning for large features, and tickets you can delegate across Claude,
# Codex, and Antigravity: grilling / to-spec / to-tickets / implementation / tdd /
# debugging / ticket-review, plus AGENTS.md and scripts/tasks_status.py.
#
# This tier assumes the memory bank is already installed in the target (decisions.md,
# patterns.md, troubleshooting.md — the workflow skills read and cite them). See
# https://github.com/TranThanh96/claude_memory_bank if it isn't yet.
#
# Behavior: same rules as claude_memory_bank's install.sh -- files that don't exist are
# copied as-is; existing files are never overwritten except with --upgrade, which
# refreshes template-owned files unless they have uncommitted changes. AGENTS.md is
# special-cased: if the target already has one, the template is staged as
# AGENTS.md.template with a merge prompt, since a script can't safely merge markdown.

set -euo pipefail

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_DIR="${INIT_TICKET_WORKFLOW_TEMPLATE:-$SELF_DIR}"
UPGRADE=0
while [[ "${1:-}" == --* ]]; do
  case "$1" in
    --upgrade) UPGRADE=1 ;;
    *) echo "error: unknown flag $1" >&2; exit 1 ;;
  esac
  shift
done
TARGET_DIR="${1:-.}"

if [[ ! -f "$TEMPLATE_DIR/AGENTS.md" || ! -d "$TEMPLATE_DIR/.claude/skills/grilling" ]]; then
  echo "error: template not found at $TEMPLATE_DIR (set INIT_TICKET_WORKFLOW_TEMPLATE to override)" >&2
  exit 1
fi
command -v python3 >/dev/null || echo "warning: python3 not found on PATH; tasks_status.py needs it." >&2

mkdir -p "$TARGET_DIR"

if [[ ! -d "$TARGET_DIR/.claude/memory" ]]; then
  cat <<'EOF' >&2
warning: no .claude/memory/ found in the target -- the workflow skills (grilling, tdd,
debugging, ...) read and cite decisions.md/patterns.md/troubleshooting.md there. Install
the memory bank first: https://github.com/TranThanh96/claude_memory_bank
Proceeding anyway.
EOF
fi

FILES=(
  "AGENTS.md"
  ".claude/routing.example.json"
  ".claude/rules/workflow.md"
  ".claude/skills/grilling/SKILL.md"
  ".claude/skills/to-spec/SKILL.md"
  ".claude/skills/to-tickets/SKILL.md"
  ".claude/skills/implementation/SKILL.md"
  ".claude/skills/tdd/SKILL.md"
  ".claude/skills/debugging/SKILL.md"
  ".claude/skills/ticket-review/SKILL.md"
  "scripts/tasks_status.py"
)

MERGE_FILES=("AGENTS.md")
# Owned by the template, not the project: --upgrade may replace these.
TEMPLATE_OWNED=(
  ".claude/routing.example.json"
  ".claude/rules/workflow.md"
  ".claude/skills/grilling/SKILL.md"
  ".claude/skills/to-spec/SKILL.md"
  ".claude/skills/to-tickets/SKILL.md"
  ".claude/skills/implementation/SKILL.md"
  ".claude/skills/tdd/SKILL.md"
  ".claude/skills/debugging/SKILL.md"
  ".claude/skills/ticket-review/SKILL.md"
  "scripts/tasks_status.py"
)

# True when replacing the file could lose work: uncommitted or untracked
# changes, or no git repo to recover from.
has_local_changes() {
  local out
  out="$(git -C "$TARGET_DIR" status --porcelain -- "$1" 2>/dev/null)" || return 0
  [[ -n "$out" ]]
}

created=()
skipped=()
staged=()
updated=()
kept=()
outdated=0

for file in "${FILES[@]}"; do
  src="$TEMPLATE_DIR/$file"
  dst="$TARGET_DIR/$file"

  if [[ -f "$dst" ]]; then
    if [[ $UPGRADE -eq 1 && " ${TEMPLATE_OWNED[*]} " == *" $file "* ]] && ! cmp -s "$src" "$dst"; then
      if has_local_changes "$file"; then
        kept+=("$file")
      else
        cp "$src" "$dst"
        updated+=("$file")
      fi
    elif [[ " ${MERGE_FILES[*]} " == *" $file "* ]]; then
      cp "$src" "$dst.template"
      staged+=("$file")
    else
      skipped+=("$file")
      if [[ " ${TEMPLATE_OWNED[*]} " == *" $file "* ]] && ! cmp -s "$src" "$dst"; then
        outdated=$((outdated + 1))
      fi
    fi
    continue
  fi

  mkdir -p "$(dirname "$dst")"
  cp "$src" "$dst"
  created+=("$file")
done

chmod +x "$TARGET_DIR/scripts"/*.py 2>/dev/null || true

echo "== claude_ticket_workflow install: $TARGET_DIR =="
echo "created:"
for f in "${created[@]:-}"; do [[ -n "$f" ]] && echo "  + $f"; done
echo "skipped (already exists):"
for f in "${skipped[@]:-}"; do [[ -n "$f" ]] && echo "  = $f"; done
if [[ $outdated -gt 0 ]]; then
  echo "  ($outdated of these differ from the template's version; re-run with --upgrade to update them)"
fi
if [[ $UPGRADE -eq 1 ]]; then
  echo "updated to the template's version (review with: git diff):"
  for f in "${updated[@]:-}"; do [[ -n "$f" ]] && echo "  ^ $f"; done
  if [[ ${#kept[@]} -gt 0 ]]; then
    echo "NOT updated, the file has uncommitted changes (commit or stash them, then re-run):"
    for f in "${kept[@]}"; do echo "  ! $f"; done
  fi
fi

if [[ ${#staged[@]} -gt 0 ]]; then
  echo
  echo "Already existed, template staged as <file>.template (NOT overwritten):"
  for f in "${staged[@]}"; do echo "  ~ $f.template"; done
  cat <<'EOF'

Hand this prompt to your coding agent:
---
Merge the staged *.template files into their originals, then delete the .template files.
- AGENTS.md: keep every existing line; append the template's pointer lines (to .claude/rules/
  and .claude/skills/implementation/SKILL.md) if they aren't already there in some form.
Show me all diffs before finishing.
---
EOF
fi

echo
echo "Next: copy .claude/routing.example.json to .claude/routing.json (fill in codex/antigravity"
echo "model names once you've used them)."
