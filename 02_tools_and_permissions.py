"""
Example 2 — A tiny coding agent: real tools, a sandbox, and permissions.

New ideas on top of Example 1:
  * A system prompt that tells the model who it is and where it works.
  * Tools that touch the real world (files, shell) — confined to a workspace folder.
  * A permission layer: read-only tools run freely, risky ones ask you first.
    This is the same idea as Claude Code's "allow / ask / deny" permission rules.
  * A REPL, so the conversation (and the model's memory of it) persists across prompts.

Run:  python 02_tools_and_permissions.py            (works inside ./workspace)
Try:  "create a python script that prints the first 10 primes, then run it"
"""
import subprocess
from pathlib import Path

from harness_common import MODEL, block_to_dict, make_client, print_text_blocks

WORKSPACE = Path("workspace").resolve()

SYSTEM = f"""You are a careful coding assistant working in {WORKSPACE}.
Use the tools to inspect files before changing them. Keep answers short."""

TOOLS = [
    {"name": "list_dir", "description": "List files in a directory (relative to the workspace).",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    {"name": "read_file", "description": "Read a text file.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    {"name": "write_file", "description": "Create or overwrite a text file.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                      "required": ["path", "content"]}},
    {"name": "bash", "description": "Run a shell command in the workspace. 30s timeout.",
     "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
]

# Permission policy: tool name -> "allow" | "ask" | "deny"
PERMISSIONS = {"list_dir": "allow", "read_file": "allow", "write_file": "ask", "bash": "ask"}


def safe_path(rel):
    """Refuse any path that escapes the workspace (e.g. '../../etc/passwd')."""
    p = (WORKSPACE / rel).resolve()
    if p != WORKSPACE and WORKSPACE not in p.parents:
        raise PermissionError(f"{rel} is outside the workspace")
    return p


def execute(name, args):
    try:
        if name == "list_dir":
            return "\n".join(sorted(x.name + ("/" if x.is_dir() else "") for x in safe_path(args["path"]).iterdir())) or "(empty)"
        if name == "read_file":
            return safe_path(args["path"]).read_text()[:20_000]
        if name == "write_file":
            p = safe_path(args["path"])
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(args["content"])
            return f"Wrote {len(args['content'])} chars to {args['path']}"
        if name == "bash":
            r = subprocess.run(args["command"], shell=True, cwd=WORKSPACE, capture_output=True, text=True, timeout=30)
            return f"exit={r.returncode}\n{r.stdout}{r.stderr}"[:20_000]
        return f"Unknown tool {name}"
    except Exception as e:  # errors go BACK to the model so it can recover
        return f"Error: {type(e).__name__}: {e}"


def check_permission(name, args, ask=input):
    policy = PERMISSIONS.get(name, "deny")
    if policy == "allow":
        return True, ""
    if policy == "deny":
        return False, "This tool is not allowed."
    answer = ask(f"\n🔐 Allow {name} {args}? [y/N] ").strip().lower()
    return (answer == "y"), "The user declined this action. Ask them what to do instead."


class Agent:
    def __init__(self, client=None, ask=input):
        self.client = client or make_client()
        self.ask = ask
        self.messages = []
        WORKSPACE.mkdir(exist_ok=True)

    # --- extension points (Examples 3 and 4 override these) ---------------
    def before_request(self):
        """Called before every model call. Example 3 compacts context here."""

    def after_response(self, resp):
        """Called after every model call. Example 3 tracks token usage here."""

    def run_tool(self, block):
        """Permission check + execution for one tool_use block. Returns (output, is_error)."""
        ok, reason = check_permission(block["name"], block["input"], self.ask)
        return (execute(block["name"], block["input"]), False) if ok else (reason, True)

    def should_stop(self):
        """Called when the model wants to finish. Return a string to make it keep going."""
        return None

    # --- the loop -----------------------------------------------------------
    def send(self, prompt, max_turns=25):
        self.messages.append({"role": "user", "content": prompt})
        for _ in range(max_turns):
            self.before_request()
            resp = self.client.messages.create(
                model=MODEL, max_tokens=4096, system=SYSTEM, tools=TOOLS, messages=self.messages
            )
            self.after_response(resp)
            content = [block_to_dict(b) for b in resp.content]
            self.messages.append({"role": "assistant", "content": content})
            print_text_blocks(content)

            if resp.stop_reason != "tool_use":
                nudge = self.should_stop()
                if not nudge:
                    return
                self.messages.append({"role": "user", "content": nudge})
                continue

            results = []
            for b in content:
                if b["type"] != "tool_use":
                    continue
                out, is_error = self.run_tool(b)
                print(f"🔧 {b['name']} -> {out[:200]!r}")
                results.append({"type": "tool_result", "tool_use_id": b["id"], "content": out,
                                "is_error": is_error})
            self.messages.append({"role": "user", "content": results})


if __name__ == "__main__":
    agent = Agent()
    print(f"Mini coding agent in {WORKSPACE}. Ctrl+C to quit.")
    while True:
        agent.send(input("\n> "))
