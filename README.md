# dcs: durable context for AI agents, in one file

**The SQLite of agent memory.** A tiny, zero-dependency, tamper-evident store for the context an agent needs to survive across sessions, restarts, and machines.

One file on disk. Python standard library only. MIT.

```python
from dcs import Context

ctx = Context("agent.dcs")              # open or create one portable file
ctx.append("user", "Book me a flight to NYC")
ctx.append("assistant", "Searching flights...")
ctx.set("pref.seat", "aisle")           # durable key/value state

# ...new process, a week later...
ctx = Context("agent.dcs")
ctx.messages(limit=20)                   # resume: recent log, ready for an LLM
ctx.get("pref.seat")                    # "aisle"
ctx.verify()                             # True: nothing was corrupted or tampered with
```

That's the whole idea. Your agent now remembers, across runs, in a file you can copy, commit, diff, and trust.

## Why

Every agent needs to remember what happened across sessions. Today you either:

- **reinvent it badly**: hand-rolled JSON blobs, a pickle file, a `messages` list you forget to persist; or
- **adopt a heavy dependency**: a hosted memory service or a framework's memory module that drags in a stack, an account, and a vendor.

There's no small, neutral, *boring* primitive for "durable agent context." `dcs` is that primitive: a single file, no dependencies, no server, no account, and because every entry is hash-chained, you can prove the record wasn't silently altered.

## Features

- **Zero dependencies.** Pure Python standard library (`sqlite3`, `json`, `hashlib`). Nothing to install but the file.
- **One portable file.** A `.dcs` file *is* a SQLite database. Move it, commit it, ship it, inspect it with any SQLite tool.
- **Append-only log + key/value state.** The durable record of what happened, plus the facts your agent keeps.
- **Tamper-evident.** Every entry is SHA-256 hash-chained to the previous one. `verify()` catches any altered, reordered, or dropped entry.
- **Resume is just reopening the file.** No special "load" ceremony.
- **LLM-ready.** `messages()` hands you `[{"role", "content"}]` straight into a model call.
- **Tiny.** ~150 lines you can read in one sitting.

## Install

```bash
pip install dcs        # see note below on the distribution name
```

Or just **copy `dcs.py` into your project**: it's a single file with no dependencies.

> Note: reference implementation; confirm the final PyPI distribution name before publishing.

## API

```python
ctx = Context("agent.dcs")           # open/create

# durable append-only log
ctx.append(role, content) -> seq     # content = any JSON-serializable value
ctx.history(limit=None, role=None)   # [{seq, ts, role, content}], oldest-first
ctx.messages(limit=None, roles=None) # [{"role","content"}] for an LLM call
ctx.head()                           # hash of the latest entry
len(ctx); for e in ctx: ...

# durable key/value state
ctx.set(key, value); ctx.get(key, default=None)
ctx.delete(key); ctx.state()         # full snapshot

# integrity
ctx.verify(raise_on_fail=False)      # walk the hash chain

ctx.close()                          # or use `with Context(...) as ctx:`
```

## It's just SQLite, no lock-in

A `.dcs` file is a normal SQLite database. Inspect it with anything:

```bash
sqlite3 agent.dcs "select seq, role, content from log order by seq;"
```

Your data is never trapped. That's the point.

## Why not Mem0 / Zep / Letta / LangChain memory?

Those are good, *bigger* tools: semantic memory, vector recall, hosted services, framework integration. Reach for them when you need that.

`dcs` is deliberately the layer underneath: the **boring, durable, portable record** of an agent's context, with **zero dependencies and tamper-evidence**, that you can drop into anything (including those tools) without taking on a stack or a vendor. It does one thing. Most agents need that one thing first.

## Integrity model

`dcs` is **tamper-evident**, not tamper-proof. Each entry's hash commits to the previous entry's hash, so any in-place edit, reordering, or deletion of a historical entry makes `verify()` return `False`. What it does *not* do on its own: stop someone with write access from rewriting the whole chain from scratch. Like any unanchored hash chain, catching that requires pinning a known-good head somewhere external (sign it, or store the latest `head()` elsewhere).

It is also **not** an encryption layer: a `.dcs` file is plaintext SQLite, readable by anyone who has it. Treat it like any data file: don't put secrets in it unless the file itself is protected.

## Status

v0.1, small on purpose, and it will stay that way: the cleanest possible durable-context primitive. Reference implementation of the **Durable Context Spine** (DCS): https://github.com/drewmattie-code/Durable-Context-Spine

## License

MIT © Drew Mattie
