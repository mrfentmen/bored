"""Bored's lockwork: what to do when nobody's asking.

A bored agent doesn't sit idle — it uses downtime productively. It consolidates
accumulated memories into structured form, explores areas that haven't been checked,
and prepares for likely upcoming tasks. Unlike curious (which seeks specific gaps),
bored does general productive work during idle time.

Parsing is rules, not vibes: consolidation groups memories by topic and deduplicates;
exploration scans a directory and reports what it found; preparation identifies needed
context and pre-fetches it. Nothing here reads a model's mind.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


def consolidate(memories: list[dict]) -> list[dict]:
    """Group memories by topic, deduplicate, return consolidated list."""
    if not memories:
        return []
    # Group by first word of fact (simple topic extraction)
    groups: dict[str, list[dict]] = {}
    for m in memories:
        fact = m.get("fact", "")
        topic = fact.split()[0].lower() if fact.split() else "unknown"
        # Strip common prefixes
        for prefix in ("the", "a", "an", "it", "this", "that"):
            if topic == prefix and len(fact.split()) > 1:
                topic = fact.split()[1].lower()
        groups.setdefault(topic, []).append(m)
    # Deduplicate within groups (keep first occurrence)
    consolidated = []
    for topic, items in groups.items():
        seen_facts = set()
        for item in items:
            fact = item.get("fact", "")
            if fact in seen_facts:
                continue
            seen_facts.add(fact)
            consolidated.append({"topic": topic, "fact": fact,
                                "source": item.get("source", "unknown"),
                                "count": sum(1 for i in items if i.get("fact") == fact)})
    return consolidated


def explore(path: str) -> dict:
    """Scan a directory and report what's there. Returns findings dict."""
    root = Path(path)
    findings = {"path": str(root), "files": [], "dirs": [], "recent": [], "summary": ""}
    if not root.is_dir():
        findings["summary"] = f"not a directory: {path}"
        return findings
    try:
        for p in sorted(root.iterdir()):
            if p.name.startswith("."):
                continue
            if p.is_dir():
                findings["dirs"].append(p.name + "/")
            else:
                findings["files"].append(p.name)
    except OSError as e:
        findings["summary"] = f"error scanning: {e}"
        return findings
    # Recent files by mtime
    try:
        files = [p for p in root.rglob("*") if p.is_file()
                 and not any(part.startswith(".") for part in p.relative_to(root).parts)]
        files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        findings["recent"] = [str(p.relative_to(root)) for p in files[:5]]
    except OSError:
        pass
    n_files = len(findings["files"])
    n_dirs = len(findings["dirs"])
    findings["summary"] = (f"found {n_files} files and {n_dirs} directories"
                           + (f", {len(findings['recent'])} recently touched" if findings["recent"] else ""))
    return findings


def render_explore(findings: dict) -> str:
    lines = [f"explore: {findings['path']}", f"  {findings['summary']}"]
    if findings["dirs"]:
        lines.append("  dirs: " + ", ".join(findings["dirs"][:10]))
    if findings["files"]:
        lines.append("  files: " + ", ".join(findings["files"][:15]))
    if findings["recent"]:
        lines.append("  recent: " + ", ".join(findings["recent"]))
    return "\n".join(lines)


def prepare(task: str, cwd: str) -> dict:
    """Identify needed context for a task and pre-fetch it. Returns prep dict."""
    root = Path(cwd or ".")
    prep = {"task": task, "needed": [], "found": [], "missing": []}
    low = (task or "").lower()
    # Identify needed context from task keywords
    if any(w in low for w in ("test", "tests", "testing")):
        prep["needed"].append("test files")
        test_dirs = [d for d in ("tests", "test", "spec") if (root / d).is_dir()]
        if test_dirs:
            prep["found"].extend(test_dirs)
        else:
            prep["missing"].append("no test directory found")
    if any(w in low for w in ("readme", "doc", "docs", "documentation")):
        prep["needed"].append("documentation")
        if (root / "README.md").is_file():
            prep["found"].append("README.md")
        else:
            prep["missing"].append("no README.md found")
    if any(w in low for w in ("config", "settings", "env")):
        prep["needed"].append("configuration")
        for f in ("package.json", "pyproject.toml", ".env", "config.yaml", "config.json"):
            if (root / f).is_file():
                prep["found"].append(f)
        if not any((root / f).is_file() for f in ("package.json", "pyproject.toml", ".env", "config.yaml", "config.json")):
            prep["missing"].append("no config files found")
    if any(w in low for w in ("git", "commit", "branch", "history")):
        prep["needed"].append("git history")
        try:
            log = subprocess.run(["git", "log", "--oneline", "-3"], cwd=str(root),
                                 capture_output=True, text=True, timeout=5)
            if log.returncode == 0 and log.stdout.strip():
                prep["found"].append("git log (last 3 commits)")
            else:
                prep["missing"].append("no git history found")
        except (OSError, subprocess.TimeoutExpired):
            prep["missing"].append("git not available")
    if not prep["needed"]:
        prep["needed"].append("general context")
        prep["found"].append("repo root: " + str(root))
    return prep


def render_prepare(prep: dict) -> str:
    lines = [f"prepare: {prep['task']}", f"  needed: {', '.join(prep['needed'])}"]
    if prep["found"]:
        lines.append(f"  found: {', '.join(prep['found'])}")
    if prep["missing"]:
        lines.append(f"  missing: {', '.join(prep['missing'])}")
    if not prep["missing"]:
        lines.append("  ready to go.")
    return "\n".join(lines)


def render_consolidated(consolidated: list[dict]) -> str:
    if not consolidated:
        return "nothing to consolidate (no memories accumulated)."
    lines = [f"consolidated {len(consolidated)} topic(s):"]
    for c in consolidated:
        lines.append(f"  - [{c['topic']}] {c['fact']} (seen {c['count']}x, source: {c['source']})")
    return "\n".join(lines)


def render_status(queue: list[dict], completed: list[dict], memories: list[dict]) -> str:
    lines = ["bored status:"]
    if queue:
        lines.append(f"  idle queue ({len(queue)}):")
        for t in queue:
            lines.append(f"    - {t.get('kind', '?')}: {t.get('detail', '')}")
    else:
        lines.append("  idle queue: (empty)")
    if completed:
        lines.append(f"  completed ({len(completed)}):")
        for t in completed:
            lines.append(f"    - {t.get('kind', '?')}: {t.get('detail', '')}")
    else:
        lines.append("  completed: (none yet)")
    lines.append(f"  memories accumulated: {len(memories)}")
    return "\n".join(lines)
