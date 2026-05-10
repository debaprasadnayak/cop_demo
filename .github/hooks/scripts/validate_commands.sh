#!/usr/bin/env bash
set -euo pipefail
# GitHub Copilot preToolUse hook — blocks dangerous operations before tool execution
# Input (stdin): {"timestamp":...,"cwd":...,"toolName":...,"toolArgs":"..."}
# Output (stdout): {"permissionDecision":"deny","permissionDecisionReason":"..."}
# Docs: https://docs.github.com/en/copilot/reference/hooks-configuration

INPUT=$(cat)

# --- Dangerous pattern groups ---
# Scoped SQL patterns: only block truly destructive DDL/DML operations
SQL_DANGEROUS='\bDROP\s+(TABLE|SCHEMA|CATALOG|DATABASE|VIEW|MATERIALIZED\s+VIEW|FUNCTION|VOLUME|SHARE|RECIPIENT|PROVIDER|CONNECTION|EXTERNAL\s+LOCATION|STORAGE\s+CREDENTIAL)\b|\bTRUNCATE\s+TABLE\b|\bDELETE\s+FROM\b'
SHELL_DANGEROUS='\brm\b|\brmdir\b|\bmkfs\b|\bshred\b|\bwipefs\b|\bfdisk\b|\bparted\b|\bdd\b[[:space:]]+if='
GIT_DANGEROUS='git[[:space:]]+(push|remote)[[:space:]]+.*--force|git[[:space:]]+reset[[:space:]]+--hard|git[[:space:]]+clean[[:space:]]+-[fdxX]'

REASON=""
if printf '%s' "$INPUT" | grep -iE "$SQL_DANGEROUS" >/dev/null 2>&1; then
  REASON="Destructive SQL operation (DROP TABLE/SCHEMA/CATALOG/DATABASE/VIEW, TRUNCATE TABLE, or DELETE FROM) is not permitted"
elif printf '%s' "$INPUT" | grep -iE "$SHELL_DANGEROUS" >/dev/null 2>&1; then
  REASON="Dangerous shell command (rm, rmdir, mkfs, shred, wipefs, fdisk, or dd) is not permitted"
elif printf '%s' "$INPUT" | grep -iE "$GIT_DANGEROUS" >/dev/null 2>&1; then
  REASON="Destructive git operation (--force push, reset --hard, or clean -f) is not permitted"
fi

if [ -n "$REASON" ]; then
  printf '{"permissionDecision":"deny","permissionDecisionReason":"%s"}\n' "$REASON"
else
  printf '{"permissionDecision":"allow"}\n'
fi
exit 0
