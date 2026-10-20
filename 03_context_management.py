"""
Example 3 — Context management: the model's memory is a budget.

Every turn resends the WHOLE conversation. Long sessions eventually hit the
context window, get slow, and get expensive. Harnesses fight this two ways:

  1. Truncate big tool outputs before they ever enter the history
     (a 50,000-line log is mostly noise to the model).
  2. Compact: when the conversation gets large, ask the model to summarize
     the older part and replace it with the summary. This is what Claude
     Code's /compact (and auto-compact) does.

The tricky detail: never cut between a tool_use and its tool_result —
the API rejects a tool_result with no matching tool_use. So we only cut
right before a real user prompt (a plain string message).

Run:  python 03_context_management.py
Tip:  set COMPACT_AT low (e.g. 3000) to watch compaction happen quickly.
"""
import importlib
import os

from harness_common import MODEL

base = importlib.import_module("02_tools_and_permissions")

MAX_TOOL_OUTPUT = 4_000  # characters
COMPACT_AT = int(os.environ.get("COMPACT_AT", 60_000))  # input tokens


def truncate(text, limit=MAX_TOOL_OUTPUT):
    """Keep the head and tail — errors usually live at the end of output."""
    if len(text) <= limit:
        return text
    half = limit // 2
    return f"{text[:half]}\n\n... [{len(text) - limit} chars truncated] ...\n\n{text[-half:]}"


def render(messages):
    """Flatten history into plain text for the summarizer."""
    lines = []
    for m in messages:
        if isinstance(m["content"], str):
            lines.append(f"{m['role'].upper()}: {m['content']}")
            continue
        for b in m["content"]:
            if b["type"] == "text":
                lines.append(f"{m['role'].upper()}: {b['text']}")
            elif b["type"] == "tool_use":
                lines.append(f"TOOL CALL {b['name']}: {b['input']}")
            elif b["type"] == "tool_result":
                lines.append(f"TOOL RESULT: {truncate(str(b['content']), 500)}")
    return "\n".join(lines)


class CompactingAgent(base.Agent):
    last_input_tokens = 0

    def after_response(self, resp):
        self.last_input_tokens = resp.usage.input_tokens
        print(f"   📊 context: {self.last_input_tokens:,} tokens")

    def run_tool(self, block):
        out, is_error = super().run_tool(block)
        return truncate(out), is_error

    def before_request(self):
        if self.last_input_tokens >= COMPACT_AT:
            self.compact()

    def compact(self):
        # Find the most recent real user prompt; everything before it gets summarized.
        cut = max((i for i, m in enumerate(self.messages)
                   if m["role"] == "user" and isinstance(m["content"], str)), default=0)
        if cut == 0:
            return  # nothing older to summarize yet
        old, keep = self.messages[:cut], self.messages[cut:]

        summary = self.client.messages.create(
            model=MODEL, max_tokens=1500,
            messages=[{"role": "user", "content":
                       "Summarize this agent session so work can continue. Keep: the user's goals, "
                       "decisions made, files created or changed, and open problems.\n\n" + render(old)}],
        ).content[0].text

        keep[0] = {"role": "user", "content":
                   f"[Summary of earlier conversation]\n{summary}\n\n[Current request]\n{keep[0]['content']}"}
        self.messages = keep
        self.last_input_tokens = 0
        print(f"   🗜️  compacted {len(old)} messages into a summary")


if __name__ == "__main__":
    agent = CompactingAgent()
    print(f"Compacting agent (compacts at {COMPACT_AT:,} tokens). Ctrl+C to quit.")
    while True:
        agent.send(input("\n> "))
