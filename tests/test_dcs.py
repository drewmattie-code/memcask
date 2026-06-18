"""Tests for dcs: zero dependencies, stdlib unittest.

Run from the repo root:  python -m unittest discover -s tests
"""
import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import dcs  # noqa: E402
from dcs import Context, IntegrityError  # noqa: E402


class DcsTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "t.dcs")

    def ctx(self):
        return Context(self.path)

    # -- log -------------------------------------------------------------------
    def test_append_and_len(self):
        c = self.ctx()
        self.assertEqual(len(c), 0)
        s1 = c.append("user", "hi")
        s2 = c.append("assistant", "hello")
        self.assertEqual((s1, s2), (1, 2))
        self.assertEqual(len(c), 2)
        c.close()

    def test_history_order_limit_and_role(self):
        c = self.ctx()
        for i in range(5):
            c.append("user" if i % 2 == 0 else "assistant", f"m{i}")
        hist = c.history()
        self.assertEqual([h["content"] for h in hist], ["m0", "m1", "m2", "m3", "m4"])
        self.assertEqual([h["content"] for h in c.history(limit=2)], ["m3", "m4"])
        self.assertEqual([h["content"] for h in c.history(role="user")], ["m0", "m2", "m4"])
        c.close()

    def test_structured_content_roundtrips(self):
        c = self.ctx()
        payload = {"flights": [{"to": "NYC", "price": 412}], "ok": True}
        c.append("tool", payload)
        self.assertEqual(c.history()[0]["content"], payload)
        c.close()

    def test_messages_format(self):
        c = self.ctx()
        c.append("user", "hi")
        c.append("tool", {"x": 1})
        msgs = c.messages()
        self.assertEqual(msgs[0], {"role": "user", "content": "hi"})
        self.assertEqual(msgs[1]["role"], "tool")
        self.assertIsInstance(msgs[1]["content"], str)  # non-str content encoded
        self.assertEqual(c.messages(roles=["user"]), [{"role": "user", "content": "hi"}])
        c.close()

    # -- state -----------------------------------------------------------------
    def test_state_set_get_default_delete(self):
        c = self.ctx()
        self.assertIsNone(c.get("missing"))
        self.assertEqual(c.get("missing", 7), 7)
        c.set("pref.seat", "aisle")
        c.set("count", 3)
        self.assertEqual(c.get("pref.seat"), "aisle")
        self.assertEqual(c.state(), {"pref.seat": "aisle", "count": 3})
        c.set("count", 4)  # upsert
        self.assertEqual(c.get("count"), 4)
        self.assertTrue(c.delete("count"))
        self.assertFalse(c.delete("count"))
        self.assertIsNone(c.get("count"))
        c.close()

    # -- durability (the whole point) -----------------------------------------
    def test_persists_across_reopen(self):
        c = self.ctx()
        c.append("user", "remember me")
        c.set("k", "v")
        head = c.head()
        c.close()

        c2 = Context(self.path)  # new process simulation
        self.assertEqual(len(c2), 1)
        self.assertEqual(c2.history()[0]["content"], "remember me")
        self.assertEqual(c2.get("k"), "v")
        self.assertEqual(c2.head(), head)
        c2.append("assistant", "still here")  # chain continues correctly
        self.assertTrue(c2.verify())
        c2.close()

    # -- integrity -------------------------------------------------------------
    def test_verify_intact(self):
        c = self.ctx()
        for i in range(10):
            c.append("user", {"i": i})
        self.assertTrue(c.verify())
        self.assertTrue(c.verify(raise_on_fail=True))
        c.close()

    def test_verify_detects_tampering(self):
        c = self.ctx()
        c.append("user", "transfer $10")
        c.append("assistant", "ok")
        c.close()
        # tamper directly in the DB, bypassing the API
        raw = sqlite3.connect(self.path)
        raw.execute("UPDATE log SET content=? WHERE seq=1", ('"transfer $1000000"',))
        raw.commit()
        raw.close()

        c2 = Context(self.path)
        self.assertFalse(c2.verify())
        with self.assertRaises(IntegrityError):
            c2.verify(raise_on_fail=True)
        c2.close()

    def test_empty_verifies(self):
        c = self.ctx()
        self.assertTrue(c.verify())
        c.close()

    # -- ergonomics ------------------------------------------------------------
    def test_context_manager_and_repr(self):
        with Context(self.path) as c:
            c.append("user", "hi")
            self.assertIn("entries=1", repr(c))

    def test_iter(self):
        c = self.ctx()
        c.append("user", "a")
        c.append("user", "b")
        self.assertEqual([e["content"] for e in c], ["a", "b"])
        c.close()

    def test_version(self):
        self.assertTrue(dcs.__version__)


if __name__ == "__main__":
    unittest.main()
