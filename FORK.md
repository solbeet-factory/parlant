# Solbeet fork of Parlant

This repository is a **minimal** fork of [emcie-co/parlant](https://github.com/emcie-co/parlant)
used by [solbeet-factory/parlant-service](https://github.com/solbeet-factory/parlant-service)
(issue #103). Upstream's default branch (`develop`) is mirrored untouched; our work lives on
`solbeet/<minor>.x` branches.

Two rules:

1. **Minimal.** A commit enters the fork only if parlant-service needs it in production and it
   cannot be done from outside the engine (hooks, container overrides, configuration). Policy
   specific to our product stays in parlant-service.
2. **Upstream first.** Every generic commit gets a pull request to `emcie-co/parlant` (drafts in
   [`docs/upstream-prs/`](docs/upstream-prs/), opened after review). When upstream merges it, the
   commit becomes a backport and disappears on the next sync.

## Branches, tags and versions

| what | value |
|---|---|
| branch | `solbeet/3.3.x` (default branch of this fork, so the scheduled sync check runs) |
| upstream base | tag `v3.3.2` (`UPSTREAM_BASE` in `src/parlant/solbeet.py`) |
| package version | `3.3.2+solbeet.N` (PEP 440 local version: installable from git/archive, not publishable to PyPI, on purpose) |
| git tag | `v3.3.2-solbeet.N` (`+` replaced by `-` so the tag is safe in URLs) |

Tags are never moved or deleted: parlant-service pins one. A new fork release is a new `N`.

Consumers install the tag's source archive (no `git` needed in the image):

```
parlant @ https://github.com/solbeet-factory/parlant/archive/refs/tags/v3.3.2-solbeet.1.tar.gz
```

`parlant.solbeet` exposes `FORK_VERSION` and `FEATURES` (one entry per commit) so the consumer
can fail at startup if the installed engine is not the fork or lacks a change it relies on.

## Commits on top of v3.3.2 (`v3.3.2-solbeet.1`)

| commit | kind | upstream |
|---|---|---|
| backport #817 tag-association version drift | backport | merged on develop 2026-06-22 |
| backport #820 Mongo startup migration (streams, rewrites only migrated docs) | backport | merged on develop 2026-06-25 |
| backport #822 batch deserialization / parallel entity loading (adapted to 3.3.2) | backport | merged on develop 2026-06-26 |
| `perf(db)` optional flush window for `JSONFileDocumentDatabase` | ours | draft [01](docs/upstream-prs/01-json-flush-window.md) |
| `feat(engine)` `on_cancelled` hook | ours | draft [02](docs/upstream-prs/02-on-cancelled-hook.md) |
| `fix(engine)` `manual` wins on conflicting session modes | ours | draft [03](docs/upstream-prs/03-manual-mode-precedence.md) |
| `fix(sessions)` `process()` without status event reports ready | ours | draft [04](docs/upstream-prs/04-process-without-status-event.md) |
| `fix(canned)` tolerant canned response ID resolution | ours | draft [05](docs/upstream-prs/05-canned-response-id-resolution.md) |
| `chore(fork)` version marker | fork only | never (re-done on every sync) |
| tests, CI, this file | fork only | never |

Not backported: emcie-co/parlant#830 (embedding cache version stamp; still open). It only matters
for an embedding cache that holds `0.1.0` documents; parlant-service's cache lives on the pod's
ephemeral disk and is always written at `0.2.0`.

## CI

- `solbeet-ci.yml` (push/PR on `solbeet/**`, fork tags): checks the branch sits on
  `UPSTREAM_BASE`, the tag matches `FORK_VERSION`, ruff on the files the fork touches, and a
  deterministic subset of the upstream suite plus `tests/solbeet` against a Mongo 7 service.
  Most upstream tests call an LLM and need keys this public fork does not hold.
- `solbeet-sync-check.yml` (monthly, or by hand): runs `scripts/solbeet_sync_check.py` against
  the latest upstream release and against `develop`, comments the report on the open
  `upstream-sync` issue (new upstream commits classified fix/perf/feature/other, and which fork
  commits apply, are already upstream, or conflict), and **fails if a fork commit does not apply
  on the latest release**.
- Upstream's `ci-test`, `lint` and `docker-publish` workflows are disabled in this fork.

## Sync with upstream

When upstream releases (the monthly issue says so), or a fix on `develop` is needed:

1. Read the `upstream-sync` issue: what upstream shipped, which of our commits are already
   upstream, which conflict.
2. `git fetch upstream --tags` and create `solbeet/<new-minor>.x` (or stay on the current branch
   for a patch release) from the new upstream tag.
3. Cherry-pick, oldest first, the fork commits that are **not** already upstream
   (`python scripts/solbeet_sync_check.py --target <tag>` lists them). Resolve conflicts in the
   commit itself; never stack "fix the rebase" commits.
4. Re-do the version marker commit: `UPSTREAM_BASE`, `FORK_VERSION = "<x.y.z>+solbeet.1"`,
   `BRANCH`, `FEATURES`, and `pyproject.toml`'s `version`.
5. Run the fork CI, tag `v<x.y.z>-solbeet.1`, push branch and tag.
6. In parlant-service: bump the archive URL in `requirements.txt` and `REQUIRED_FEATURES` if a
   feature changed, run the full suite, open the PR.

To ship a new fix on the current base: add the commit (with a `parlant.solbeet.FEATURES` entry),
bump `FORK_VERSION`/`pyproject` to `+solbeet.N+1`, tag `v3.3.2-solbeet.N+1`.

## Upstream PRs

Drafts live in `docs/upstream-prs/`. To open one: branch from `upstream/develop`, cherry-pick the
commit (it may need adapting: `develop` moved after 3.3.2), add `Signed-off-by` (upstream requires
the [DCO](DCO.md)), push to this fork and open the PR against `emcie-co/parlant:develop` with the
draft as body. Record the PR URL in the draft and in the table above.
