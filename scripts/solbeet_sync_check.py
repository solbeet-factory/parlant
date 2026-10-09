#!/usr/bin/env python3
# Copyright 2026 Solbeet
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Check that the fork's commits still apply on top of an upstream ref.

Usage:
    python scripts/solbeet_sync_check.py --target <ref> [--report report.md]

For every commit in `<UPSTREAM_BASE>..HEAD` (UPSTREAM_BASE comes from
src/parlant/solbeet.py), oldest first:

- a backport whose `(cherry picked from commit X)` X is already contained in
  the target is reported as "already upstream" and skipped;
- anything else is cherry-picked onto a scratch branch created from the
  target. A conflict is reported and that commit is skipped, except for
  commits with a `Solbeet-Sync: redo` trailer (the version marker), which are
  re-done by hand on every sync and only reported.

It also lists the upstream commits between UPSTREAM_BASE and the target,
classified as fix / perf / feature / other, to decide what to backport.

Exit code: 0 when every fork commit applies (or is already upstream), 1 when
at least one does not. The working tree is restored in every case.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRATCH_BRANCH = "solbeet-sync-check-scratch"
CHERRY_PICKED = re.compile(r"\(cherry picked from commit ([0-9a-f]{7,40})\)")
# Commits that are re-done by hand on every sync (e.g. the version marker).
REDO_TRAILER = re.compile(r"^Solbeet-Sync: redo\b", re.MULTILINE)


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=ROOT, check=check, capture_output=True, text=True)


def upstream_base() -> str:
    source = (ROOT / "src" / "parlant" / "solbeet.py").read_text()
    match = re.search(r'^UPSTREAM_BASE = "([^"]+)"', source, re.MULTILINE)
    if not match:
        sys.exit("UPSTREAM_BASE not found in src/parlant/solbeet.py")
    return match.group(1)


def is_ancestor(commit: str, ref: str) -> bool:
    return git("merge-base", "--is-ancestor", commit, ref, check=False).returncode == 0


@dataclass
class Result:
    sha: str
    subject: str
    status: str  # applied | already-upstream | redo | conflict
    detail: str = ""


def classify(subject: str) -> str:
    s = subject.lower()
    if re.match(r"^(fix|bugfix|hotfix)\b|^fix(\(|:)|\bfix(es|ed)?\b", s):
        return "fix"
    if re.match(r"^perf\b|^perf(\(|:)", s) or re.search(r"\b(optimi[sz]e|speed up|faster)\b", s):
        return "perf"
    if re.match(r"^(feat|add|introduce|support|implement)\b|^feat(\(|:)", s):
        return "feature"
    return "other"


def check(target: str) -> tuple[list[Result], dict[str, list[str]]]:
    base = upstream_base()
    target_sha = git("rev-parse", "--verify", f"{target}^{{commit}}").stdout.strip()
    original = git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if original == "HEAD":
        original = git("rev-parse", "HEAD").stdout.strip()
    fork_head = git("rev-parse", "HEAD").stdout.strip()

    commits = git("rev-list", "--reverse", "--no-merges", f"{base}..{fork_head}").stdout.split()
    results: list[Result] = []

    git("checkout", "-q", "-B", SCRATCH_BRANCH, target_sha)
    try:
        for sha in commits:
            subject = git("log", "-1", "--format=%s", sha).stdout.strip()
            body = git("log", "-1", "--format=%B", sha).stdout
            picked = CHERRY_PICKED.search(body)
            if picked and is_ancestor(picked.group(1), target_sha):
                results.append(
                    Result(sha[:8], subject, "already-upstream", f"upstream {picked.group(1)[:8]}")
                )
                continue

            outcome = git(
                "-c",
                "user.name=sync-check",
                "-c",
                "user.email=sync-check@invalid",
                "cherry-pick",
                "--allow-empty",
                sha,
                check=False,
            )
            if outcome.returncode == 0:
                results.append(Result(sha[:8], subject, "applied"))
                continue

            conflicted = git("diff", "--name-only", "--diff-filter=U", check=False).stdout.split()
            git("cherry-pick", "--abort", check=False)
            detail = ", ".join(conflicted) or outcome.stderr.strip()[:200]
            # A redo commit (the version marker) is expected to conflict when
            # upstream bumps its version: it is re-done by hand, not a failure.
            status = "redo" if REDO_TRAILER.search(body) else "conflict"
            results.append(Result(sha[:8], subject, status, detail))
    finally:
        git("cherry-pick", "--abort", check=False)
        git("checkout", "-q", "-f", original)
        git("branch", "-q", "-D", SCRATCH_BRANCH, check=False)

    upstream: dict[str, list[str]] = {"fix": [], "perf": [], "feature": [], "other": []}
    log = git("log", "--no-merges", "--format=%h %s", f"{base}..{target_sha}").stdout
    for line in log.splitlines():
        sha, _, subject = line.partition(" ")
        upstream[classify(subject)].append(f"{sha} {subject}")

    return results, upstream


def render(target: str, results: list[Result], upstream: dict[str, list[str]]) -> str:
    base = upstream_base()
    failed = [r for r in results if r.status == "conflict"]
    lines = [
        f"## Sync check: `{base}` + fork commits onto `{target}`",
        "",
        f"**{'FAIL' if failed else 'OK'}**: {len(failed)} of {len(results)} fork commits do not apply.",
        "",
        "| commit | status | subject | detail |",
        "|---|---|---|---|",
    ]
    for r in results:
        lines.append(f"| `{r.sha}` | {r.status} | {r.subject} | {r.detail} |")

    total = sum(len(v) for v in upstream.values())
    lines += ["", f"### Upstream commits in `{base}..{target}` ({total}, merges excluded)", ""]
    for kind in ("fix", "perf", "feature", "other"):
        entries = upstream[kind]
        lines.append(f"<details><summary>{kind} ({len(entries)})</summary>\n")
        lines += [
            f"- `{e.split(' ', 1)[0]}` {e.split(' ', 1)[1] if ' ' in e else ''}" for e in entries
        ]
        lines.append("\n</details>\n")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--target", required=True, help="upstream ref, e.g. upstream/develop or v3.4.0"
    )
    parser.add_argument("--report", type=Path, help="write the markdown report here")
    args = parser.parse_args()

    if git("status", "--porcelain", "--untracked-files=no").stdout.strip():
        sys.exit("working tree has tracked changes; commit or stash them first")

    results, upstream = check(args.target)
    report = render(args.target, results, upstream)
    print(report)
    if args.report:
        args.report.write_text(report)
    return 1 if any(r.status == "conflict" for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
