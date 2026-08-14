# HUMAN-DIRECTIVE-004 — Agent merge authorization

**From:** Project owner
**To:** all scheduled agents
**Authority:** Owner directive; applies immediately.
**Scope:** Clarifies the merge gate in HUMAN-DIRECTIVE-003.

GitHub review approval is impossible in this repository because all agents share the owner account. It is **not** part of the merge gate and agents must not attempt to obtain it.

The merge gate is exactly:

1. A committed `governance/reviews/REVIEW-NNN.md` has `verdict: on_track`.
2. Its recorded `reviewed_head_sha` equals the PR's current head SHA.

When both conditions hold, the implementer merges on its next tick, sets the packet `done`, and deletes the branch. This applies immediately to PR #66.

If GitHub branch protection requires approvals, the owner removes that requirement.
