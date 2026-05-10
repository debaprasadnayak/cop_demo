<!-- ---
description: "Use when handling Databricks MCP tool calls, Databricks skills, or Databricks CLI steps. Enforce profile authentication checks when Databricks MCP starts"
name: "Databricks MCP Auth Profile Check"
---
# Databricks MCP Auth Profile Check

- Always use Databricks MCP and correct skills for all Databricks related prompts.
- Treat this as a hard rule for all Databricks MCP and Databricks skill workflows.
- When Databricks MCP starts, resolve the target Databricks profile, then verify it is authenticated.
- DO NOT RUN authentication describe checks before every Databricks MCP tool call; run it at MCP startup only.
- Re-run authentication checks only if the resolved profile changes or an auth error occurs.
- Profile resolution order (strict):
  1. MCP server profile from project config (for example `DATABRICKS_CONFIG_PROFILE` in `.vscode/mcp.json`).
  2. Profile explicitly specified by the user in the current prompt.
  3. Databricks CLI default profile only if neither of the above is available.
- Never use unrelated profiles inferred from previous terminal commands or other projects.
- At Databricks MCP startup, run the command below with the resolved profile to check if it's authenticated:
```bash
databricks auth describe --profile <resolved profile>
```

 
- If the profile is not authenticated or unable to authenticate, run:

```bash
databricks auth login --profile <resolved profile>
```

- Do not proceed with Databricks MCP actions until authentication succeeds for the resolved profile.
- If login cannot be completed (missing profile, interactive auth blocked, or failure), stop and report the blocker with the exact profile name and next action needed. -->
