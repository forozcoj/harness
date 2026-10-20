"""
Offline tests: a fake "model" replays scripted responses so you can test the
harness without an API key. Testing your loop with fake responses is a core
harness-engineering habit.

Run:  python test_offline.py
"""
import importlib
import os
import shutil
from types import SimpleNamespace as NS

os.chdir(os.path.dirname(os.path.abspath(__file__)))
ex1 = importlib.import_module("01_minimal_loop")
ex2 = importlib.import_module("02_tools_and_permissions")
ex3 = importlib.import_module("03_context_management")
ex4 = importlib.import_module("04_hooks")


def text(t):
    return NS(type="text", text=t)


def tool(id_, name, **inp):
    return NS(type="tool_use", id=id_, name=name, input=inp)


class FakeClient:
    """Returns scripted responses in order and records every request."""

    def __init__(self, script, tokens=100):
        self.script, self.calls, self.tokens = list(script), [], tokens
        self.messages = self

    def create(self, **kw):
        self.calls.append(kw)
        content = self.script.pop(0)
        stop = "tool_use" if any(b.type == "tool_use" for b in content) else "end_turn"
        return NS(content=content, stop_reason=stop, usage=NS(input_tokens=self.tokens))


def fresh_workspace():
    shutil.rmtree(ex2.WORKSPACE, ignore_errors=True)


def test_minimal_loop():
    fake = FakeClient([[tool("t1", "calculator", expression="2340*0.175+99")], [text("It's 508.5")]])
    msgs = ex1.agent("q", client=fake)
    assert msgs[2]["content"][0]["content"] == "508.5"
    assert len(fake.calls) == 2


def test_permissions_and_sandbox():
    fresh_workspace()
    fake = FakeClient([
        [tool("a", "write_file", path="hi.py", content="print('hi')")],   # user says yes
        [tool("b", "bash", command="python3 hi.py")],                      # user says no
        [tool("c", "read_file", path="../../etc/passwd")],                 # escapes sandbox
        [text("done")],
    ])
    answers = iter(["y", "n"])
    a = ex2.Agent(client=fake, ask=lambda _: next(answers))
    a.send("go")
    results = [m["content"][0] for m in a.messages if m["role"] == "user" and isinstance(m["content"], list)]
    assert "Wrote" in results[0]["content"]
    assert results[1]["is_error"] and "declined" in results[1]["content"]
    assert "outside the workspace" in results[2]["content"]


def test_truncation_and_compaction():
    fresh_workspace()
    assert "truncated" in ex3.truncate("x" * 10_000)
    ex3.COMPACT_AT = 50
    fake = FakeClient([[text("first answer")], [text("SUMMARY")], [text("second answer")]], tokens=100)
    a = ex3.CompactingAgent(client=fake)
    a.send("first question")
    a.send("second question")   # tokens >= 50 -> compaction before this request
    assert len(a.messages) == 2
    assert "SUMMARY" in a.messages[0]["content"] and "second question" in a.messages[0]["content"]
    ex3.COMPACT_AT = 60_000


def test_hooks():
    fresh_workspace()
    fake = FakeClient([
        [tool("a", "bash", command="sudo rm -rf /")],                              # PreToolUse blocks
        [tool("b", "write_file", path="bad.py", content="def x(:\n")],             # PostToolUse flags
        [text("All done!")],                                                       # Stop hook refuses
        [tool("c", "write_file", path="bad.py", content="def x():\n    pass\n")],
        [text("Fixed, done.")],                                                    # Stop hook passes
    ])
    a = ex4.HookedAgent(client=fake, ask=lambda _: "y")
    a.send("go")
    flat = str(a.messages)
    assert "Blocked by policy" in flat
    assert "does not compile" in flat
    assert "You can't finish yet" in flat
    assert len(fake.calls) == 5
    assert (ex2.WORKSPACE / ".audit.jsonl").read_text().count("\n") == 3


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"✅ {name}")
    fresh_workspace()
    print("All offline tests passed.")
