# Databricks Codespace

This repository hosts a Databricks AI Dev Tool workspace.
The demo project is in `cop_demo/`.

## 1) Install Databricks AI Dev Tool

### Prerequisites

1. Install Claude Code

mac:
```bash
curl -fsSL https://claude.ai/install.sh | bash
```

win:
```powershell
irm https://claude.ai/install.ps1 | iex
```

2. Install Git

mac:
```bash
brew install git
```

win:
```powershell
winget install --id Git.Git -e
```

3. Install Databricks CLI

mac:
```bash
brew tap databricks/tap && brew install databricks
```

win:
```powershell
winget install --id Databricks.DatabricksCLI -e
```

4. Install uv

mac:
```bash
brew install uv
```

win:
```powershell
winget install --id astral-sh.uv -e
```

5. Install Python 3.14.3

mac/win:
```bash
uv python install 3.14.3
```

6. Create Databricks OAuth profile

mac/win:
```bash
databricks auth login --host <workspace-url>
```

7. Login to named Databricks profile

mac/win:
```bash
databricks auth login --host <workspace-url> --profile <profile-name>
```

8. Install Databricks AI Dev Kit

mac:
```bash
bash <(curl -sL https://raw.githubusercontent.com/databricks-solutions/ai-dev-kit/main/install.sh)
```

win:
```powershell
irm https://raw.githubusercontent.com/databricks-solutions/ai-dev-kit/main/install.ps1 | iex
```

Note: You need at least one supported tool, for example GitHub Copilot, Claude Code, Antigravity, OpenAI Codex, Cursor, or Gemini CLI.

## 2) Agents in this workspace

- `databricks-dataengineer.agent`: `.github/agents/databricks-dataengineer.agent.md`
- `support-analytics-reporter`: `.github/agents/support-analytics-reporter.md`

## 3) Hooks configured and why enforced

Hook config: `.github/hooks/hook.json`

- `sessionStart`
  - Runs ai-dev-kit plugin update check script at session start.
  - 5-second timeout so session startup is not blocked.
- `userPromptSubmitted`
  - Validates prompts and denies destructive SQL, dangerous shell commands, and destructive git operations.
- `preToolUse`
  - Applies the same destructive-command guard right before tool calls.

Why enforced:
- Workspace rule in `.github/copilot-instructions.md` treats hooks as a hard gate.
- Agent must not bypass deny decisions.
- If blocked, agent should stop and explain a safer alternative.
- Without the instruction, copilot was bypassing the hook in version 1.0.44

## 4) Skills and tools in this workspace

Skills:
- Located in `.github/skills/`
- Includes Databricks-focused skills (jobs, DBSQL, pipelines, Unity Catalog, vector search, Genie, dashboards, MLflow, and more).

Tools:
- MCP config in `.mcp.json`
- Databricks MCP server is configured and uses `DATABRICKS_CONFIG_PROFILE` from that file.

How `sessionStart` relates to MCP updates:
- `sessionStart` runs `.claude-plugin/check_update` from ai-dev-kit.
- This updates/checks ai-dev-kit plugin components used by the workspace tooling.
- It does not directly rewrite `.mcp.json`; it keeps the local ai-dev-kit integration current so MCP-backed capabilities remain up to date.

## 5) How to use prompt files

Prompt folder:
- `.github/prompts/`

Current prompt file:
- `.github/prompts/plan-norwayWeatherLiveDemo.prompt.md`

Quick usage:
1. Open the prompt file in your editor.
2. Select **Agents** mode in Copilot Chat.
3. Click **Run Prompt** from the prompt file or ask copilot to run it with any additional instructions e.g skip GO/NO-GO gates.
4. Follow GO/NO-GO gates in the prompt and approve each step.
5. Use `cop_demo/project-docs/norwayWeatherLiveDemo.highlevel-checklist.md` as the live run status tracker.

## Project demo

For demo run and data pipeline details, see: `cop_demo/README.md`.
