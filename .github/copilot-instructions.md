# Hook Enforcement Before Requests

- Treat the workspace hook configuration as a hard gate before working on user requests.
- Check the active hook definition in `.github/hooks/hook.json` whenever hook behavior is relevant, unclear, or could affect the requested action.
- Do not bypass, work around, or retry past a deny decision returned by the `userPromptSubmitted` or `preToolUse` hooks.
- If a hook blocks an action, stop and tell the user what category was blocked and what safer alternative is available.
- Pay special attention to requests that may trigger destructive SQL, destructive shell commands, or destructive git operations because the workspace hook validator already screens those.
- If workspace instructions, user instructions, and hook behavior conflict, follow the hook outcome and surface the conflict explicitly.
- Run a databricks auth login if there is an authentication error while using the Databricks MCP only using the profile from MCP config. 
  ```bash
databricks auth login --profile <auth profile from MCP config or user prompt>
```