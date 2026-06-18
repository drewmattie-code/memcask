"""memcask: durable context for AI agents, in one file.

The SQLite of agent memory: a tiny, zero-dependency, tamper-evident store for the
context an agent needs to survive across sessions, restarts, and machines.

    from memcask import Context

    ctx = Context("agent.cask")          # open or create one portable file
    ctx.append("user", "Book me a flight to NYC")
    ctx.append("assistant", "Searching flights...")
    ctx.set("pref.seat", "aisle")       # durable key/value state

    # ...new process, days later...
    ctx = Context("agent.cask")
    ctx.messages(limit=20)              # resume: recent log as LLM messages
    ctx.get("pref.seat")               # "aisle"
    ctx.verify()                        # True: hash chain intact

One file on disk. Standard library only. MIT licensed.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from typing import Any, Iterator, Optional

__version__ = "0.1.0"
__all__ = ["Context", "IntegrityError"]

SCHEMA_VERSION = 1
GENESIS_HASH = "0" * 64


class IntegrityError(Exception):
    """Raised by ``verify(raise_on_fail=True)`` when the hash chain is broken
    (data corruption or tampering)."""


def _canon(content: Any) -> str:
    """Deterministic JSON encoding so the hash is stable across runs/machines."""
    return json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _entry_hash(prev_hash: str, ts: float, role: str, content_json: str) -> str:
    h = hashlib.sha256()
    h.update(prev_hash.encode("utf-8"))
    h.update(f"{ts:.6f}".encode("utf-8"))
    h.update(role.encode("utf-8"))
    h.update(content_json.encode("utf-8"))
    return h.hexdigest()


class Context:
    """A durable, portable, tamper-evident context store backed by a single
    SQLite file.

    Two surfaces:

    * an **append-only log** (the durable record of what happened): ``append``,
      ``history``, ``messages``, iteration, ``len``;
    * **key/value state** (facts the agent keeps and updates): ``set``, ``get``,
      ``state``, ``delete``.

    Every log entry is hash-chained to the one before it, so ``verify()`` can
    detect any silent corruption or tampering.
    """

    def __init__(self, path: str = "context.cask"):
        self.path = path
        self._db = sqlite3.connect(path, isolation_level=None)  # autocommit; append() uses an explicit IMMEDIATE txn
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=NORMAL")
        self._init_schema()

    # -- setup -----------------------------------------------------------------
    def _init_schema(self) -> None:
        db = self._db
        db.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        db.execute(
            "CREATE TABLE IF NOT EXISTS log ("
            " seq INTEGER PRIMARY KEY AUTOINCREMENT,"
            " ts REAL NOT NULL,"
            " role TEXT NOT NULL,"
            " content TEXT NOT NULL,"      # canonical JSON
            " prev_hash TEXT NOT NULL,"
            " hash TEXT NOT NULL)"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS state ("
            " key TEXT PRIMARY KEY,"
            " value TEXT NOT NULL,"        # JSON
            " updated REAL NOT NULL)"
        )
        db.execute(
            "INSERT OR IGNORE INTO meta(key,value) VALUES('schema_version',?)",
            (str(SCHEMA_VERSION),),
        )
        db.execute(
            "INSERT OR IGNORE INTO meta(key,value) VALUES('created',?)",
            (repr(time.time()),),
        )
        db.commit()

    # -- append-only log -------------------------------------------------------
    def append(self, role: str, content: Any) -> int:
        """Append an entry to the durable log and return its sequence number.

        ``content`` may be any JSON-serializable value (a string, a tool result
        dict, a list, ...). The entry is hash-chained to the previous one.
        """
        ts = time.time()
        cj = _canon(content)
        db = self._db
        db.execute("BEGIN IMMEDIATE")  # take the write lock BEFORE reading head, so two
        try:                           # concurrent writers can't chain off the same entry
            prev = self.head()
            h = _entry_hash(prev, ts, role, cj)
            cur = db.execute(
                "INSERT INTO log(ts,role,content,prev_hash,hash) VALUES(?,?,?,?,?)",
                (ts, role, cj, prev, h),
            )
            db.execute("COMMIT")
            return int(cur.lastrowid)
        except Exception:
            db.execute("ROLLBACK")
            raise

    def head(self) -> str:
        """Hash of the most recent log entry (``GENESIS_HASH`` if empty)."""
        row = self._db.execute("SELECT hash FROM log ORDER BY seq DESC LIMIT 1").fetchone()
        return row[0] if row else GENESIS_HASH

    def history(self, limit: Optional[int] = None, role: Optional[str] = None) -> list[dict]:
        """Return log entries oldest-first as dicts ``{seq, ts, role, content}``.

        ``limit`` returns only the most recent N entries; ``role`` filters by role.
        """
        q = "SELECT seq,ts,role,content FROM log"
        args: list[Any] = []
        if role is not None:
            q += " WHERE role=?"
            args.append(role)
        q += " ORDER BY seq ASC"
        rows = self._db.execute(q, args).fetchall()
        if limit is not None:
            rows = rows[-limit:]
        return [{"seq": s, "ts": t, "role": r, "content": json.loads(c)} for (s, t, r, c) in rows]

    def messages(self, limit: Optional[int] = None, roles: Optional[list[str]] = None) -> list[dict]:
        """Return the log as ``[{"role", "content"}]`` ready to hand to an LLM.

        Non-string content is JSON-encoded. ``roles`` keeps only those roles.
        """
        out = []
        for e in self.history(limit=limit):
            if roles is not None and e["role"] not in roles:
                continue
            c = e["content"]
            out.append({"role": e["role"], "content": c if isinstance(c, str) else _canon(c)})
        return out

    # -- key/value state -------------------------------------------------------
    def set(self, key: str, value: Any) -> None:
        """Set durable key/value state (upsert). ``value`` is any JSON value."""
        self._db.execute(
            "INSERT INTO state(key,value,updated) VALUES(?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated=excluded.updated",
            (key, json.dumps(value, ensure_ascii=False), time.time()),
        )
        self._db.commit()

    def get(self, key: str, default: Any = None) -> Any:
        row = self._db.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def delete(self, key: str) -> bool:
        """Delete a state key. Returns True if it existed."""
        cur = self._db.execute("DELETE FROM state WHERE key=?", (key,))
        self._db.commit()
        return cur.rowcount > 0

    def state(self) -> dict:
        """Snapshot of all key/value state."""
        return {k: json.loads(v) for (k, v) in self._db.execute("SELECT key,value FROM state").fetchall()}

    # -- integrity -------------------------------------------------------------
    def verify(self, raise_on_fail: bool = False) -> bool:
        """Walk the hash chain. Returns True if intact; False (or raises
        ``IntegrityError``) if any entry was altered, reordered, or dropped."""
        prev = GENESIS_HASH
        for (seq, ts, role, cj, prev_hash, h) in self._db.execute(
            "SELECT seq,ts,role,content,prev_hash,hash FROM log ORDER BY seq ASC"
        ):
            if prev_hash != prev or _entry_hash(prev_hash, ts, role, cj) != h:
                if raise_on_fail:
                    raise IntegrityError(f"hash chain broken at seq={seq}")
                return False
            prev = h
        return True

    # -- lifecycle / dunder ----------------------------------------------------
    def __len__(self) -> int:
        return int(self._db.execute("SELECT COUNT(*) FROM log").fetchone()[0])

    def __iter__(self) -> Iterator[dict]:
        return iter(self.history())

    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> "Context":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"Context(path={self.path!r}, entries={len(self)})"
