#!/usr/bin/env bash
# Move Claude Code CLI chat history for THIS repo between your own machines.
#
# Claude Code stores each terminal session as a .jsonl transcript under
#   ~/.claude/projects/<project-slug>/
# where <project-slug> is the repo's absolute path with every non-alphanumeric
# character replaced by '-'. That slug differs per machine, so this script
# recomputes it on each side instead of copying the folder name verbatim.
#
#   export (old machine):  ./tools/claude_sessions.sh export
#                          -> ~/gp-claude-sessions.zip   (transfer this file)
#   import (new machine):  ./tools/claude_sessions.sh import ~/gp-claude-sessions.zip
#                          then:  cd <repo> && claude --resume
#
# Same Claude account on both machines is assumed (authenticate normally).
set -euo pipefail

action="${1:-}"
zip_arg="${2:-}"
[ "$action" = export ] || [ "$action" = import ] || {
  echo "usage: $0 export|import [zipfile]" >&2; exit 2; }

repo="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
abs="$(cd "$repo" && pwd)"
# Claude Code is a NATIVE app: it slugifies the OS-native path. On Git Bash/
# MSYS the bash path is /c/Users/... -> slug -c-Users-... but Claude uses the
# Windows path C:\Users\... -> slug C--Users-... . Convert before slugifying so
# the import folder matches what `claude --resume` reads.
if command -v cygpath >/dev/null 2>&1; then
  abs="$(cygpath -w "$abs")"
fi
slug="$(printf '%s' "$abs" | sed 's/[^A-Za-z0-9]/-/g')"
proj="$HOME/.claude/projects/$slug"

if [ "$action" = export ]; then
  [ -d "$proj" ] || { echo "No Claude sessions at $proj" >&2; exit 1; }
  out="${zip_arg:-$HOME/gp-claude-sessions.zip}"
  rm -f "$out"
  ( cd "$proj" && zip -q -r "$out" ./*.jsonl )
  echo "Exported $(ls "$proj"/*.jsonl | wc -l) session(s) -> $out"
  echo "Transfer that .zip to the other machine, then run the import."
else
  [ -n "$zip_arg" ] && [ -f "$zip_arg" ] || {
    echo "pass the zip path: $0 import <gp-claude-sessions.zip>" >&2; exit 1; }
  mkdir -p "$proj"
  unzip -o -q "$zip_arg" -d "$proj"
  echo "Imported into $proj"
  echo "Now: cd '$abs' && claude --resume   ($(ls "$proj"/*.jsonl | wc -l) sessions)"
fi
