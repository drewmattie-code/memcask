"""Quickstart: an agent that remembers across runs.

Run it twice:
    python examples/quickstart.py
    python examples/quickstart.py   # <- resumes from the first run

The whole point: the second run picks up the thread, from one portable file.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dcs import Context  # noqa: E402


def fake_llm(messages):
    """Stand-in for a real model call (swap in your client of choice)."""
    return f"(model reply, having seen {len(messages)} prior messages)"


def main():
    ctx = Context("demo_agent.dcs")

    if len(ctx) == 0:
        print("First run: starting fresh.")
        ctx.append("user", "Plan a trip to Tokyo.")
        ctx.set("destination", "Tokyo")
    else:
        print(f"Resuming: {len(ctx)} prior entries, destination = {ctx.get('destination')!r}")

    reply = fake_llm(ctx.messages(limit=10))
    ctx.append("assistant", reply)

    print("assistant:", reply)
    print("integrity:", "OK" if ctx.verify() else "BROKEN")
    print(f"context file: {ctx.path}  (run again to resume; delete it to reset)")
    ctx.close()


if __name__ == "__main__":
    main()
