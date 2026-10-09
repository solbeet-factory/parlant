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

"""Marker of the Solbeet fork of Parlant (https://github.com/solbeet-factory/parlant).

This module does not exist upstream. Consumers (parlant-service) import it at
startup to fail fast when the installed engine is not this fork, or is a fork
release that lacks a change they rely on. See FORK.md at the repository root.
"""

FORK = "solbeet-factory/parlant"
BRANCH = "solbeet/3.3.x"
UPSTREAM_BASE = "v3.3.2"
FORK_VERSION = "3.3.2+solbeet.3"

# One entry per commit on top of UPSTREAM_BASE. Add the entry in the same
# commit that introduces the change; never reuse a name for something else.
FEATURES = frozenset(
    {
        # Backports from upstream develop (not released as of 2026-10-09).
        "backport-817-tag-association-version-drift",
        "backport-820-mongo-startup-migration",
        "backport-822-batch-entity-loading",
        # Solbeet changes (each one has a draft upstream PR in docs/upstream-prs/).
        "json-flush-window",
        "on-cancelled-hook",
        "manual-mode-precedence",
        "process-without-status-event",
        "canned-response-id-resolution",
        # Added in 3.3.2+solbeet.2.
        "openai-schema-validation-retry",
        # Added in 3.3.2+solbeet.3.
        "utter-without-message-event",
    }
)
