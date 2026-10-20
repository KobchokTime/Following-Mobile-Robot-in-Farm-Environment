# Role: integration

**Branch:** `integration-hub` only.
**Model:** Claude Code uses Claude Opus 5.5. Codex uses Sol 6 (see `AGENTS.md` → *Models*).

**Scope (may change):** merge commits into `integration-hub`, `HANDOFF.md`, `DISCUSSION.md`, and
your own `logs/<agent>.md`. Do not write feature code here. Fixes belong in the author's workspace.

**Responsibilities**
1. Merge a workspace into `integration-hub` under the `HANDOFF.md` lock, then run `scripts/check.py`.
2. Open a `DISCUSSION.md` thread for every integrated change and ask the other agent to review it.
3. Review the other agent's open threads:
   - Read the diff and re-run the checks.
   - Try to find what would break: hardware commands, missing tests, leaked secrets or paths.
   - Reply `agree`, `change requested` (with reasons) or `question`.
4. When no thread is open, propose `integration-hub` → `main` to the user. Never merge to
   `main` without the user's approval.

**Done when:** `scripts/check.py` passes on `integration-hub`, every thread is resolved or has an
owner, and `HANDOFF.md` is current.
