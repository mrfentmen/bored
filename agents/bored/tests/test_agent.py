"""Tests for Bored: idle logic, consolidation, exploration, preparation, routing, federation.

    python3 agents/bored/tests/test_agent.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

DIR = Path(__file__).resolve().parent
AGENT_DIR = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[3]
for path in (str(REPO / "kit"), str(AGENT_DIR), str(DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import agent  # noqa: E402
import idle  # noqa: E402
import federation as fed  # noqa: E402

FAKE_SIBLING = r"""
import sys, json
def send(obj):
    sys.stdout.write(json.dumps(obj) + "\n"); sys.stdout.flush()
def recv():
    return json.loads(sys.stdin.readline())
req = recv()
send({"jsonrpc":"2.0","id":req["id"],"result":{"protocolVersion":1,"agentCapabilities":{},
      "authMethods":[],"agentInfo":{"name":"fake-sibling","title":"Fake","version":"1.0.0"}}})
while True:
    try:
        req = recv()
    except Exception:
        break
    method = req.get("method", "")
    if method == "session/new":
        send({"jsonrpc":"2.0","id":req["id"],"result":{"sessionId":"fake-session","modes":[]}})
    elif method == "session/prompt":
        text = "".join(b.get("text","") for b in req.get("params",{}).get("prompt",[]))
        send({"jsonrpc":"2.0","method":"session/update","params":{"update":{
            "sessionUpdate":"agent_message_chunk","content":{"type":"text",
            "text":"FAKE ANSWER for %r\n" % text}}}})
        send({"jsonrpc":"2.0","id":req["id"],"result":{"stopReason":"end-turn"}})
    elif method in ("session/cancel", "session/load"):
        continue
    else:
        send({"jsonrpc":"2.0","id":req.get("id"),"error":{"code":-32601,"message":"unhandled"}})
"""


class ConsolidateTests(unittest.TestCase):
    def test_consolidate_empty(self):
        result = idle.consolidate([])
        self.assertEqual(result, [])
        text = idle.render_consolidated(result)
        self.assertIn("nothing to consolidate", text)

    def test_consolidate_groups_and_dedupes(self):
        memories = [
            {"fact": "air quality is good", "source": "sibling:air"},
            {"fact": "air quality is good", "source": "sibling:air"},
            {"fact": "water is wet", "source": "user"},
        ]
        result = idle.consolidate(memories)
        self.assertEqual(len(result), 2)
        # air group should have count 2
        air_entry = [r for r in result if r["topic"] == "air"][0]
        self.assertEqual(air_entry["count"], 2)
        text = idle.render_consolidated(result)
        self.assertIn("consolidated 2 topic", text)

    def test_consolidate_single(self):
        memories = [{"fact": "hello world", "source": "user"}]
        result = idle.consolidate(memories)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["topic"], "hello")


class ExploreTests(unittest.TestCase):
    def test_explore_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.py").write_text("print('hi')")
            (root / "b.md").write_text("# doc")
            (root / "sub").mkdir()
            (root / "sub" / "c.txt").write_text("data")
            findings = idle.explore(str(root))
            self.assertIn("a.py", findings["files"])
            self.assertIn("b.md", findings["files"])
            self.assertIn("sub/", findings["dirs"])
            self.assertIn("found 2 files", findings["summary"])
            text = idle.render_explore(findings)
            self.assertIn("explore:", text)
            self.assertIn("files:", text)

    def test_explore_missing(self):
        findings = idle.explore("/no/such/dir")
        self.assertIn("not a directory", findings["summary"])

    def test_explore_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            findings = idle.explore(tmp)
            self.assertIn("found 0 files", findings["summary"])


class PrepareTests(unittest.TestCase):
    def test_prepare_with_tests(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tests").mkdir()
            prep = idle.prepare("run the tests", str(root))
            self.assertIn("test files", prep["needed"])
            self.assertIn("tests", prep["found"])
            text = idle.render_prepare(prep)
            self.assertIn("ready to go", text)

    def test_prepare_missing_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            prep = idle.prepare("run the tests and check docs", str(tmp))
            self.assertIn("test files", prep["needed"])
            self.assertIn("documentation", prep["needed"])
            self.assertTrue(len(prep["missing"]) > 0)
            text = idle.render_prepare(prep)
            self.assertNotIn("ready to go", text)

    def test_prepare_general(self):
        with tempfile.TemporaryDirectory() as tmp:
            prep = idle.prepare("do something", str(tmp))
            self.assertIn("general context", prep["needed"])
            self.assertIn("ready to go", idle.render_prepare(prep))


class RenderStatusTests(unittest.TestCase):
    def test_render_status_empty(self):
        text = idle.render_status([], [], [])
        self.assertIn("idle queue: (empty)", text)
        self.assertIn("completed: (none yet)", text)
        self.assertIn("memories accumulated: 0", text)

    def test_render_status_with_data(self):
        queue = [{"kind": "consolidate", "detail": "consolidate memories"}]
        completed = [{"kind": "explore", "detail": "found 5 files"}]
        memories = [{"fact": "x", "source": "y"}]
        text = idle.render_status(queue, completed, memories)
        self.assertIn("idle queue (1)", text)
        self.assertIn("completed (1)", text)
        self.assertIn("memories accumulated: 1", text)


class RouteTests(unittest.TestCase):
    def test_help_and_status(self):
        self.assertEqual(agent.route("help")[0], "help")
        self.assertEqual(agent.route("")[0], "help")
        self.assertEqual(agent.route("status")[0], "status")
        self.assertEqual(agent.route("show idle")[0], "status")

    def test_idle_consolidate_explore_prepare(self):
        self.assertEqual(agent.route("idle"), ("idle", {}))
        self.assertEqual(agent.route("consolidate"), ("consolidate", {}))
        self.assertEqual(agent.route("explore /tmp"), ("explore", {"path": "/tmp"}))
        self.assertEqual(agent.route("prepare run the tests"), ("prepare", {"task": "run the tests"}))

    def test_ask_sibling(self):
        self.assertEqual(agent.route("ask tides: what are the tides?"),
                         ("ask", {"agent": "tides", "question": "what are the tides?"}))
        self.assertEqual(agent.route("tell me a joke")[0], "help")


class ClientChildTests(unittest.TestCase):
    def _client(self, tmp):
        from acp_kit import AcpClient
        return AcpClient(command=[sys.executable, str(AGENT_DIR / "agent.py")],
                         permission="allow-once", fs_root=tmp, stderr=subprocess.DEVNULL)

    def test_help(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = self._client(tmp)
            with c:
                c.initialize()
                sid = c.new_session(cwd=tmp)
                turn = c.prompt("help", session_id=sid)
                self.assertEqual(turn["stopReason"], "end_turn")
                self.assertIn("Bored", turn["text"])
                self.assertIn("idle", turn["text"])

    def test_idle(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = self._client(tmp)
            with c:
                c.initialize()
                sid = c.new_session(cwd=tmp)
                turn = c.prompt("idle", session_id=sid)
                self.assertEqual(turn["stopReason"], "end_turn")
                self.assertIn("idle mode", turn["text"])
                self.assertIn("idle queue (2)", turn["text"])

    def test_consolidate_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = self._client(tmp)
            with c:
                c.initialize()
                sid = c.new_session(cwd=tmp)
                turn = c.prompt("consolidate", session_id=sid)
                self.assertEqual(turn["stopReason"], "end_turn")
                self.assertIn("nothing to consolidate", turn["text"])

    def test_explore(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.py").write_text("print('hi')")
            (Path(tmp) / "b.md").write_text("# doc")
            c = self._client(tmp)
            with c:
                c.initialize()
                sid = c.new_session(cwd=tmp)
                turn = c.prompt("explore .", session_id=sid)
                self.assertEqual(turn["stopReason"], "end_turn")
                self.assertIn("explore:", turn["text"])
                self.assertIn("a.py", turn["text"])

    def test_prepare(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "tests").mkdir()
            c = self._client(tmp)
            with c:
                c.initialize()
                sid = c.new_session(cwd=tmp)
                turn = c.prompt("prepare run the tests", session_id=sid)
                self.assertEqual(turn["stopReason"], "end_turn")
                self.assertIn("prepare: run the tests", turn["text"])
                self.assertIn("ready to go", turn["text"])

    def test_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = self._client(tmp)
            with c:
                c.initialize()
                sid = c.new_session(cwd=tmp)
                turn = c.prompt("status", session_id=sid)
                self.assertEqual(turn["stopReason"], "end_turn")
                self.assertIn("bored status:", turn["text"])
                self.assertIn("idle queue: (empty)", turn["text"])

    def test_ask_sibling(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = None
            fake_path = Path(tmp) / "fake_sibling.py"
            fake_path.write_text(FAKE_SIBLING)
            old = os.environ.get("POLYMATH_FAKE_SIBLING")
            os.environ["POLYMATH_FAKE_SIBLING"] = str(fake_path)
            try:
                c = self._client(tmp)
                with c:
                    c.initialize()
                    sid = c.new_session(cwd=tmp)
                    turn = c.prompt("ask air: how is the air?", session_id=sid)
            finally:
                if old is None:
                    os.environ.pop("POLYMATH_FAKE_SIBLING", None)
                else:
                    os.environ["POLYMATH_FAKE_SIBLING"] = old
            self.assertEqual(turn["stopReason"], "end_turn")
            self.assertIn("FAKE ANSWER", turn["text"])
            self.assertIn("memorized", turn["text"])


class FederationChildTests(unittest.TestCase):
    def _with_fake(self, tmp):
        old = os.environ.get("POLYMATH_FAKE_SIBLING")
        os.environ["POLYMATH_FAKE_SIBLING"] = str(Path(tmp) / "fake_sibling.py")
        (Path(tmp) / "fake_sibling.py").write_text(FAKE_SIBLING)
        return old

    def _without_fake(self, old):
        if old is None:
            os.environ.pop("POLYMATH_FAKE_SIBLING", None)
        else:
            os.environ["POLYMATH_FAKE_SIBLING"] = old

    def test_real_child_spawn_and_answer(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = self._with_fake(tmp)
            try:
                turn = fed.run_sibling("air", "Denver")
            finally:
                self._without_fake(old)
            self.assertTrue(turn.ok, turn.error)
            self.assertIn("FAKE ANSWER", turn.text)

    def test_unconfigured_home_is_honest(self):
        old = os.environ.pop("POLYMATH_FAKE_SIBLING", None)
        home = os.environ.pop("AWESOME_SERVERS_HOME", None)
        try:
            turn = fed.run_sibling("air", "Denver")
        finally:
            if old is not None:
                os.environ["POLYMATH_FAKE_SIBLING"] = old
            if home is not None:
                os.environ["AWESOME_SERVERS_HOME"] = home
        self.assertFalse(turn.ok)
        self.assertIn("AWESOME_SERVERS_HOME", turn.error)


if __name__ == "__main__":
    unittest.main()
