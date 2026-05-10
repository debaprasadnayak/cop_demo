# GitHub Copilot PreToolUse hook — blocks dangerous operations
# VS Code sends JSON via stdin: { tool_name, tool_input, tool_use_id, ... }
# Responds with hookSpecificOutput JSON to stdout + exit 0
# Docs: https://code.visualstudio.com/docs/copilot/customization/hooks

$inputText = [System.Console]::In.ReadToEnd()

# --- Dangerous pattern groups ---
# Scoped SQL patterns: only block truly destructive DDL/DML operations
$sqlDangerous   = '\bDROP\s+(TABLE|SCHEMA|CATALOG|DATABASE|VIEW|MATERIALIZED\s+VIEW|FUNCTION|VOLUME|SHARE|RECIPIENT|PROVIDER|CONNECTION|EXTERNAL\s+LOCATION|STORAGE\s+CREDENTIAL)\b|\bTRUNCATE\s+TABLE\b|\bDELETE\s+FROM\b'
$shellDangerous = '\b(rm|rmdir|mkfs|shred|wipefs|fdisk|parted)\b|\bdd\b\s+if='
$gitDangerous   = 'git\s+(push|remote).*--force|git\s+reset\s+--hard|git\s+clean\s+-[fdxX]'

$reason = $null

if     ($inputText -imatch $sqlDangerous)   { $reason = 'Destructive SQL operation (DROP TABLE/SCHEMA/CATALOG/DATABASE/VIEW, TRUNCATE TABLE, or DELETE FROM) is not permitted' }
elseif ($inputText -imatch $shellDangerous) { $reason = 'Dangerous shell command (rm, rmdir, mkfs, shred, wipefs, fdisk, or dd) is not permitted' }
elseif ($inputText -imatch $gitDangerous)   { $reason = 'Destructive git operation (--force push, reset --hard, or clean -f) is not permitted' }

# VS Code PreToolUse hook response — must be wrapped in hookSpecificOutput
if ($reason) {
    @{
        hookSpecificOutput = @{
            hookEventName            = 'PreToolUse'
            permissionDecision       = 'deny'
            permissionDecisionReason = $reason
        }
    } | ConvertTo-Json -Compress
} else {
    Write-Output '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow"}}'
}
exit 0
