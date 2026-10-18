"""Bored: the agent that uses idle time productively.

When nobody's asking, Bored doesn't sit idle — it consolidates accumulated memories
into structured form, explores areas that haven't been checked, and prepares for
likely upcoming tasks. Unlike curious (which seeks specific gaps), bored does general
productive work during downtime.

    idle                    enter idle mode, queue productive work
    consolidate             consolidate accumulated memories into structured form
    explore <path>          explore an area (scan files, check status)
    prepare <task>          prepare for an upcoming task (pre-fetch context)
    status                  show idle work queue and completed work
    ask <sibling>: question forward to a sibling over ACP, cited

The idle work log is the whole contract: plain JSON, any tool can read it. Nothing
here reads a model's mind; idle work that cannot be done honestly is refused.

The vendored lockwork (kit, federation) carries its credit lines.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
for path in (str(REPO / "kit"), str(Path(__file__).resolve().parent)):
    if path not in sys.path:
        sys.path.insert(0, path)

from acp_kit import STOP_END_TURN, STOP_REFUSAL, AcpAgent, SessionContext, prompt_text  # noqa: E402

import idle  # noqa: E402
import federation as fed  # noqa: E402

WELCOME = (
    "I am Bored. When nobody's asking, I use the time:\n"
    "  - idle                  enter idle mode, queue productive work\n"
    "  - consolidate           consolidate accumulated memories into structured form\n"
    "  - explore <path>        explore an area (scan files, check status)\n"
    "  - prepare <task>        prepare for an upcoming task (pre-fetch context)\n"
    "  - status                show idle work queue and completed work\n"
    "  - ask tides: what are the tides?   (forward to a sibling, cited)\n"
    "Idle time is productive time. Nothing is invented."
)

_IDLE = re.compile(r"^\s*idle\b", re.I)
_CONSOLIDATE = re.compile(r"^\s*consolidate\b", re.I)
_EXPLORE = re.compile(r"^\s*explore\s+(.+?)\s*$", re.I | re.S)
_PREPARE = re.compile(r"^\s*prepare\s+(.+?)\s*$", re.I | re.S)
_STATUS = re.compile(r"^\s*(status|show|what (?:idle|done|completed))\b", re.I)
_HELP = re.compile(r"^\s*(help|what can you do)\b", re.I)
_ASK = re.compile(r"^\s*ask\s+(.+)$", re.I | re.S)


def route(text: str) -> tuple[str, dict]:
    stripped = str(text or "").strip()
    if not stripped or _HELP.search(stripped):
        return "help", {}
    if _IDLE.search(stripped):
        return "idle", {}
    if _CONSOLIDATE.search(stripped):
        return "consolidate", {}
    m = _EXPLORE.search(stripped)
    if m:
        return "explore", {"path": m.group(1).strip()}
    m = _PREPARE.search(stripped)
    if m:
        return "prepare", {"task": m.group(1).strip()}
    if _STATUS.search(stripped):
        return "status", {}
    m = _ASK.search(stripped)
    if m:
        pair = fed.ask_pair(stripped)
        if pair:
            return "ask", {"agent": pair[0], "question": pair[1]}
        return "ask", {"question": m.group(1).strip()}
    pair = fed.ask_pair(stripped)
    if pair:
        return "ask", {"agent": pair[0], "question": pair[1]}
    return "help", {}


class BoredAgent(AcpAgent):
    name = "bored"
    title = "Bored - uses idle time productively: consolidate, explore, prepare"
    version = "1.0.0"

    def new_session(self, session) -> dict:
        session.remember("agent", "Bored session opened.")
        self._queue = []
        self._completed = []
        self._memories = []
        return {}

    def prompt(self, ctx: SessionContext, prompt: list[dict]) -> str:
        text = prompt_text(prompt)
        skill, params = route(text)
        cwd = Path(ctx.session.cwd or ".")
        ctx.plan([
            (f"Take the prompt as Bored ({skill})", "high"),
            ("Do productive idle work - no inventing", "high"),
            ("Report the results honestly", "medium"),
        ])

        if skill == "help":
            ctx.stream_text(WELCOME + "\n")
            return STOP_END_TURN

        if skill == "idle":
            # Queue productive work
            self._queue = [
                {"kind": "consolidate", "detail": "consolidate accumulated memories"},
                {"kind": "explore", "detail": f"explore {cwd}"},
            ]
            ctx.stream_text("idle mode: queued productive work.\n"
                            + idle.render_status(self._queue, self._completed, self._memories) + "\n")
            return STOP_END_TURN

        if skill == "consolidate":
            result = idle.consolidate(self._memories)
            self._completed.append({"kind": "consolidate",
                                    "detail": f"consolidated {len(result)} topic(s)"})
            # remove from queue
            self._queue = [t for t in self._queue if t.get("kind") != "consolidate"]
            ctx.stream_text(idle.render_consolidated(result) + "\n")
            return STOP_END_TURN

        if skill == "explore":
            path = params["path"]
            if not Path(path).is_absolute():
                path = str(cwd / path)
            findings = idle.explore(path)
            self._completed.append({"kind": "explore", "detail": findings["summary"]})
            self._queue = [t for t in self._queue if t.get("kind") != "explore"]
            ctx.stream_text(idle.render_explore(findings) + "\n")
            return STOP_END_TURN

        if skill == "prepare":
            task = params["task"]
            prep = idle.prepare(task, str(cwd))
            self._completed.append({"kind": "prepare", "detail": f"prepared for: {task}"})
            ctx.stream_text(idle.render_prepare(prep) + "\n")
            return STOP_END_TURN

        if skill == "status":
            ctx.stream_text(idle.render_status(self._queue, self._completed, self._memories) + "\n")
            return STOP_END_TURN

        if skill == "ask":
            if "agent" in params:
                call = "call_sibling"
                ctx.tool_call(call, f"Ask the {params['agent']} sibling", kind="run",
                              name="bored-ask", raw_input=dict(params))
                ctx.tool_call_update(call, status="in_progress")
                try:
                    row = fed.run_sibling(params["agent"], params["question"])
                except fed.SiblingError as exc:
                    ctx.tool_call_update(call, status="failed",
                                         content=ctx.text_content(str(exc)[:200]))
                    ctx.message(f"the sibling missed: {exc}")
                    return STOP_END_TURN
                if not row.ok or not (row.text or "").strip():
                    ctx.tool_call_update(call, status="failed",
                                         content=ctx.text_content(row.error or "refused"))
                    ctx.message(f"the sibling missed: {row.error or 'refused'}")
                    return STOP_END_TURN
                ctx.tool_call_update(call, status="completed",
                                     content=ctx.text_content(
                                         f"{row.agent}: stopReason={row.stop_reason or 'end-turn'}"))
                # accumulate memory from sibling answer
                self._memories.append({"fact": (row.text or "").strip()[:120],
                                       "source": f"sibling:{row.agent}"})
                ctx.stream_text((row.text or "").rstrip() + "\n\n"
                                f"Source: the {row.agent} sibling over ACP. (memorized)\n")
                return STOP_END_TURN
            ctx.stream_text("no sibling named. try: ask <name>: <question>\n")
            return STOP_END_TURN

        ctx.stream_text(WELCOME + "\n")
        return STOP_END_TURN

    def on_cancel(self, session) -> None:
        return None


def main(argv=None) -> int:
    import logging
    logging.basicConfig(level="INFO", stream=sys.stderr,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    try:
        BoredAgent().run()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
