---
name: resolving-merge-conflicts
description: Resolve an in-progress Git merge or rebase while preserving the intended behavior and unrelated work.
---

# Resolve merge conflicts

Inspect Git status, the operation, original head and conflicting paths. Keep
unrelated edits out. Preserve a recovery reference before rewriting commits;
never discard user changes to obtain a clean tree.

Read each side's commits, linked issue or PR and current base behavior. Check
whether the original problem remains unresolved. A conflict-free rebase alone
does not prove an old change still belongs. Use review-delegation's PR delivery
reference when taking over or reviving existing work.

Resolve according to the requested outcome and current invariants. Preserve both
intents where compatible. Do not invent behavior to make a hunk disappear.
If the conflict exposes a material unresolved direction choice, pause dependent
resolution, retain recovery state and continue independent work. Do not force a
resolution or abort automatically. Honor an explicit request to abort after
checking that it preserves unrelated work.

Use Huyang for source reads and guarded edits. Run meaningful focused and required
checks in Chaldea with scratch HOME/TMPDIR. Stage only resolved paths owned by
this task. Continue the merge/rebase until its commits are reconciled, then
inspect the final diff and Git status.

For a rebase, compare the original and new series with git range-diff. Verify
that intended behavior survived and already-landed work was not restored.
When publication is authorized, use an explicit --force-with-lease tied to the
remote head observed before rewriting. A failed lease requires fetching and
reconciling new work, never an unqualified force push.

Finishing a merge/rebase does not itself authorize publishing, merging a PR,
closing it or changing its base. Report the result and remaining verification.
