"""
Example 4 — Hooks: deterministic code that runs at fixed points in the loop.

A prompt can ASK the model to behave; a hook GUARANTEES it. Claude Code exposes
the same events (PreToolUse, PostToolUse, Stop, ...) in settings.json, so once
you understand this file, its hooks docs will feel familiar.

  PreToolUse  -> may block a tool call before it runs (and tell the model why)
  PostToolUse -> sees the result: log it, lint it, append feedback
  Stop        -> runs when the model says "I'm done"; may send it back to work

Hooks below:
  * block_dangerous   — refuses rm -rf, sudo, curl|sh, etc.
  * audit_log         — appends every tool call to workspace/.audit.jsonl
  * syntax_check      — after a .py file is written, compiles it and reports errors
  * python_must_pass  — Stop hook: won't let the agent finish while any .py fails to compile

Run:  python 04_hooks.py
Try:  "write broken.py with a syntax error on purpose, then say you're done"
"""
import importlib
import json
import re
import subprocess
import time

base = importlib.import_module("02_tools_and_permissions")
ctx = importlib.import_module("03_context_management")
WS = base.WORKSPACE


# ---- hook implementations ---------------------------------------------------
DANGEROUS = [r"\brm\s+-[a-z]*r[a-z]*f", r"\bsudo\b", r"curl[^|]*\|\s*(ba)?sh", r"\bmkfs\b", r">\s*/dev/sd"]


def block_dangerous(name, args):
    if name == "bash":
        for pat in DANGEROUS:
            if re.search(pat, args["command"]):
                return f"Blocked by policy: command matches {pat!r}. Find a safer approach."
    return None  # None = allow


def audit_log(name, args, output, is_error):
    with open(WS / ".audit.jsonl", "a") as f:
        f.write(json.dumps({"t": time.time(), "tool": name, "args": args, "error": is_error,
                            "output": output[:300]}) + "\n")
    return None


def syntax_check(name, args, output, is_error):
    if name == "write_file" and args["path"].endswith(".py") and not is_error:
        r = subprocess.run(["python3", "-m", "py_compile", args["path"]], cwd=WS, capture_output=True, text=True)
        if r.returncode:
            return f"⚠️ Hook: {args['path']} does not compile:\n{r.stderr[-1500:]}"
    return None  # None = nothing to add


def python_must_pass():
    bad = []
    for p in WS.rglob("*.py"):
        r = subprocess.run(["python3", "-m", "py_compile", str(p)], capture_output=True, text=True)
        if r.returncode:
            bad.append(f"{p.relative_to(WS)}: {r.stderr.strip().splitlines()[-1]}")
    if bad:
        return "You can't finish yet — these files don't compile. Fix them:\n" + "\n".join(bad)
    return None


HOOKS = {
    "PreToolUse": [block_dangerous],
    "PostToolUse": [audit_log, syntax_check],
    "Stop": [python_must_pass],
}


# ---- wiring hooks into the loop ------------------------------------------------
class HookedAgent(ctx.CompactingAgent):
    max_stop_retries = 3  # a Stop hook must never trap the agent forever

    def send(self, prompt, max_turns=25):
        self._stop_retries = 0
        return super().send(prompt, max_turns)

    def run_tool(self, block):
        name, args = block["name"], block["input"]
        for hook in HOOKS["PreToolUse"]:
            reason = hook(name, args)
            if reason:
                print(f"   🛑 {hook.__name__}: {reason}")
                audit_log(name, args, reason, True)
                return reason, True

        out, is_error = super().run_tool(block)

        for hook in HOOKS["PostToolUse"]:
            extra = hook(name, args, out, is_error)
            if extra:
                print(f"   🪝 {hook.__name__} added feedback")
                out = f"{out}\n\n{extra}"
        return out, is_error

    def should_stop(self):
        if self._stop_retries >= self.max_stop_retries:
            return None
        for hook in HOOKS["Stop"]:
            nudge = hook()
            if nudge:
                self._stop_retries += 1
                print(f"   ↩️  {hook.__name__}: sending the agent back to work")
                return nudge
        return None


if __name__ == "__main__":
    agent = HookedAgent()
    print("Hooked agent. Ctrl+C to quit.")
    while True:
        agent.send(input("\n> "))
