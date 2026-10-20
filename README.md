# Agent Harness Lab

A hands-on path to understanding **agent harnesses** — the code that wraps a language
model and turns it into an agent. Claude Code is a harness. So is every "AI agent"
product. The model only produces text and tool requests; the harness decides what
tools exist, runs them, enforces rules, and manages memory.

```
           ┌──────────────────── harness ────────────────────┐
 you ──▶   │ system prompt + tools + history ──▶  MODEL       │
           │        ▲                               │         │
           │        │ tool results     tool requests ▼         │
           │   permissions ◀── hooks ◀── execute tools         │
           │        └──── context management (truncate/compact)│
           └──────────────────────────────────────────────────┘
```

## Setup

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...          # from console.anthropic.com
python test_offline.py                       # no key needed — fake model
```

Optional: `export HARNESS_MODEL=claude-haiku-5-5` for cheaper experiments.
Note: API usage is billed separately from your Claude / Claude Code subscription.

## The examples (do them in order)

| File | Idea | Claude Code equivalent |
|---|---|---|
| `01_minimal_loop.py` | The loop: call → run tools → send results → repeat | The core agent loop |
| `02_tools_and_permissions.py` | Real tools, a sandbox folder, allow/ask/deny | Permission rules, the "Allow this command?" prompt |
| `03_context_management.py` | Truncate tool output, summarize old history | `/compact` and auto-compact |
| `04_hooks.py` | Deterministic code at PreToolUse / PostToolUse / Stop | Hooks in `.claude/settings.json` |
| `test_offline.py` | Test the harness with scripted fake responses | How harnesses are tested in practice |

Each file builds on the previous one, and each is short enough to read in one sitting.
Read the docstring at the top first.

## Key lessons hidden in the code

1. **The model never runs anything.** It asks; your code decides.
2. **Errors are data.** A failed tool returns its error *to the model*, which usually fixes it.
3. **All tool results for a turn go back in one user message**, each matched by `tool_use_id`.
4. **Always have stop conditions** — `max_turns`, and a cap on Stop-hook retries.
5. **Context is a budget.** Every turn resends everything; truncate and compact.
6. **Never split a tool_use from its tool_result** when trimming history.
7. **Prompts persuade, hooks guarantee.** Put hard rules in code.

## Exercises — do these with Claude Code

Open this folder in Claude Code (`cd agent-harness-lab && claude`) and ask it to help
with each exercise. A good habit: ask it to **explain the plan first**, then implement,
then run `python test_offline.py` and add a test for the new feature.

1. **`edit_file` tool** — replace an exact string instead of rewriting whole files.
   Why do real harnesses prefer this? (Hint: tokens and accidental damage.)
2. **Project memory** — on startup, load `workspace/AGENT.md` into the system prompt.
   This is exactly what `CLAUDE.md` does for Claude Code.
3. **Streaming** — print the model's text as it arrives using `client.messages.stream`.
4. **Parallel tools** — run independent tool calls from one turn concurrently.
5. **Subagent tool** — add a `delegate(task)` tool that runs a *fresh* `Agent` with its
   own history and returns only its final answer. Notice how this protects the parent's
   context — that's why Claude Code uses subagents for big searches.
6. **Prompt caching** — add `cache_control` to the system prompt and tools; compare
   `usage` numbers before and after.
7. **Permission memory** — let the user answer "always" to stop being asked about a tool.
8. **Compare with the real thing** — add a PreToolUse hook to Claude Code itself that
   blocks `rm -rf`, in `.claude/settings.json`. Ask Claude Code to set it up and explain
   how its hook format maps to `04_hooks.py`.

## Where to go next

- Claude API tool-use docs: https://docs.claude.com/en/docs/agents-and-tools/tool-use/overview
- Claude Code hooks: https://docs.claude.com/en/docs/claude-code/hooks
- Claude Agent SDK (the harness behind Claude Code, as a library):
  https://docs.claude.com/en/docs/agent-sdk/overview — once you've built these examples,
  you'll recognize what each SDK option is doing.
