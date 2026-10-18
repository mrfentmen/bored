# Bored — the idle agent

> **Bored** doesn't sit idle. When nobody's asking, it consolidates accumulated memories
> into structured form, explores areas that haven't been checked, and prepares for likely
> upcoming tasks. Unlike curious (which seeks specific gaps), bored does general productive
> work during downtime.

The word is coined: *bored* — the rung where idle time becomes productive time.

```text
        .----.
       /  _   \
       |=[_]==|
  (`.--.____.---.'\
   `-./'\\_.'
      |  /.  .||
       \:-: .'
  LGB   `-'                     (archive piece, credited, until the portrait lands)
```

## What it does

| You say | Bored does |
|---|---|
| `idle` | enters idle mode, queues productive work (consolidate + explore) |
| `consolidate` | groups accumulated memories by topic, deduplicates, reports |
| `explore <path>` | scans a directory, reports files, dirs, recent changes |
| `prepare <task>` | pre-fetches context needed for a task (tests, docs, config, git) |
| `status` | shows idle work queue and completed work |
| `ask tides: what are the tides?` | forwards to a sibling over ACP, cited (and memorizes the answer) |

Rules: consolidation groups by topic and deduplicates. Exploration scans the filesystem.
Preparation checks for test dirs, README, config files, git history. Nothing is invented.

## Run it

```bash
npm i -g bored-agent     # or: npx bored-agent  (packaged agent; needs python3)
bored-agent              # launches agents/bored/agent.py
```

Or from source:

```bash
git clone https://github.com/mrfentmen/bored && cd bored
python3 agents/bored/agent.py
```

For forwarded questions, point it at a checkout of the answerer repo:

```bash
AWESOME_SERVERS_HOME=/path/to/awesome-servers bored-agent
```

Run the tests (23 of them, offline, including real child-process federation):

```bash
python3 agents/bored/tests/test_agent.py
```

## The honest parts

- Idle work is deterministic: consolidation groups by first word, exploration scans
  the filesystem, preparation checks for specific files. Nothing is invented.
- Vendored lockwork is credited line by line: `kit/` from the ACP kit; `federation.py`
  from the polymath — vendored on 2026-10-18, kept standalone on purpose.

Built on top of: [mrfentmen/awesome-servers](https://github.com/mrfentmen/awesome-servers)
(the watcher runtime, the feeds) and
[mrfentmen/superagents](https://github.com/mrfentmen/superagents) (the polymath and the
sentry, the first two agents this one borrows transport and lockwork from) and
[mrfentmen/fedora-hat](https://github.com/mrfentmen/fedora-hat) and
[mrfentmen/instink](https://github.com/mrfentmen/instink) and
[mrfentmen/contextink](https://github.com/mrfentmen/contextink) and
[mrfentmen/rewind](https://github.com/mrfentmen/rewind) and
[mrfentmen/scopink](https://github.com/mrfentmen/scopink) and
[mrfentmen/curious](https://github.com/mrfentmen/curious).