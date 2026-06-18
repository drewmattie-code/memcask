# Launch draft: Show HN

**Title (≤80 chars, no "I built"):**
Show HN: memcask, durable and tamper-evident context for AI agents in one file

**Body:**

I kept rewriting the same thing on every agent project: a way to persist what
the agent knows across sessions and restarts. The choices were always ad-hoc
JSON I forgot to save, or a heavy hosted memory service that wanted an account
and a stack.

So I wrote memcask, a tiny, zero-dependency Python library that keeps an agent's
durable context in a single SQLite file:

- append-only log + key/value state (the record of what happened, plus the
  facts the agent keeps)
- every entry is SHA-256 hash-chained, so `verify()` catches any silently
  altered, reordered, or dropped entry
- zero dependencies: stdlib `sqlite3` / `json` / `hashlib`
- one portable file you can copy, commit, and inspect with any SQLite tool, no
  lock-in
- resume = just reopen the file; `messages()` hands you `[{role, content}]` for
  an LLM call
- ~150 lines

It's deliberately the boring layer *under* Mem0 / Zep / LangChain memory. Most
agents need durable, trustworthy context before they need semantic recall.

It's the reference implementation of a small spec I've been writing on agent
state (the Durable Context Spine).

Repo: https://github.com/drewmattie-code/memcask · MIT.

Feedback very welcome, especially on the on-disk format and the integrity model.

---

## Posting notes
- Best window: Tue-Thu, ~8-10am ET.
- First comment (pin): paste the 6-line quickstart + the "why not Mem0/Zep" paragraph.
- Reply to every comment fast for the first 2-3 hours; engagement drives ranking.
- Cross-post after HN: LinkedIn (résumé/Spine framing), X thread, r/LocalLLaMA, r/AI_Agents.
- Live on PyPI: pip install memcask (published 2026-06-18).
