# MISSING.md — the claim-check for the bored repo

## The name, checked (2026-10-18)

Searched on GitHub (API search, repos):

- `bored` (repos): many hits — generic word.
- `bored agent` (repos): 8 hits — all noise (Valent agent, data format, parody).
- `idle agent` (repos): not searched separately; the concept of an agent that uses
  idle time productively did not appear in the bored-agent results.

The slot this repo takes — an agent that uses idle time productively (consolidate,
explore, prepare) — did not appear in those hits. The claim stays only that the
specific combination is not there.

## What this repo does NOT claim

- It does not "think" during idle time. It runs deterministic tasks (consolidate,
  explore, prepare) — no model inference.
- It does not autonomously decide what to work on. The user queues idle work; the
  agent executes it.
- It does not replace curious. Curious seeks specific gaps; bored does general
  productive work during downtime.

## What is genuinely absent (to build or not to build)

- The portrait: Yogi has the png; the README slot waits.
- Autonomous idle detection (agent detects it's idle and starts working on its own) —
  not built; the user must say "idle."
- Persistent idle work log (saving completed work across sessions) — not built.