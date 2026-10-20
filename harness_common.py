"""Small shared helpers so each example stays focused on one idea."""
import os

MODEL = os.environ.get("HARNESS_MODEL", "claude-sonnet-5-5")


def make_client():
    """Create the real Anthropic client. Needs ANTHROPIC_API_KEY in your env."""
    import anthropic  # imported lazily so the offline tests don't need it

    return anthropic.Anthropic()


def block_to_dict(block):
    """Turn an SDK content block into a plain dict we can store and resend."""
    if block.type == "text":
        return {"type": "text", "text": block.text}
    if block.type == "tool_use":
        return {"type": "tool_use", "id": block.id, "name": block.name, "input": block.input}
    return {"type": block.type}


def print_text_blocks(content):
    for b in content:
        if b["type"] == "text" and b["text"].strip():
            print(f"\n🤖 {b['text']}")
