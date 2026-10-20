"""
Example 1 — The minimal agent loop.

The whole idea of a "harness" fits in one sentence:
    call the model -> if it asked for tools, run them and send results back -> repeat
    until it answers without asking for a tool.

Everything Claude Code does (permissions, hooks, compaction, subagents) is
layered on top of this loop.

Run:  python 01_minimal_loop.py "What is 17.5% of 2,340, plus 99?"
"""
import sys

from harness_common import MODEL, block_to_dict, make_client, print_text_blocks

# 1) Describe tools to the model with a JSON schema.
TOOLS = [
    {
        "name": "calculator",
        "description": "Evaluate a basic arithmetic expression, e.g. '2340 * 0.175 + 99'.",
        "input_schema": {
            "type": "object",
            "properties": {"expression": {"type": "string"}},
            "required": ["expression"],
        },
    }
]


# 2) Implement the tools. The model never runs code; YOUR harness does.
def run_tool(name, args):
    if name == "calculator":
        allowed = set("0123456789+-*/(). ")
        expr = args["expression"]
        if not set(expr) <= allowed:
            return "Error: only numbers and + - * / ( ) are allowed"
        return str(eval(expr))  # safe-ish because of the character whitelist
    return f"Error: unknown tool {name}"


# 3) The loop.
def agent(prompt, client=None, max_turns=10):
    client = client or make_client()
    messages = [{"role": "user", "content": prompt}]

    for turn in range(max_turns):
        resp = client.messages.create(
            model=MODEL, max_tokens=1024, tools=TOOLS, messages=messages
        )
        content = [block_to_dict(b) for b in resp.content]
        messages.append({"role": "assistant", "content": content})
        print_text_blocks(content)

        if resp.stop_reason != "tool_use":
            return messages  # model is done

        # Run every tool the model asked for, then send all results back in ONE user message.
        results = []
        for b in content:
            if b["type"] == "tool_use":
                out = run_tool(b["name"], b["input"])
                print(f"🔧 {b['name']}({b['input']}) -> {out}")
                results.append({"type": "tool_result", "tool_use_id": b["id"], "content": out})
        messages.append({"role": "user", "content": results})

    print("⚠️  Hit max_turns — a real harness always needs a stop condition.")
    return messages


if __name__ == "__main__":
    agent(" ".join(sys.argv[1:]) or "What is 17.5% of 2,340, plus 99?")
