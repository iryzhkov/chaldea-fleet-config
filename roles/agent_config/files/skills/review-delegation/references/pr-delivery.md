# PR delivery and continuation

Read for PR creation, takeover, revival or review replies. This reference adapts
useful tstack ideas to our authority, review and tool rules. It adds no merge,
closure, deployment or comment-posting authority.

## Establish intent before continuing old work

Read the live PR or requested thread, user corrections, findings and current
head/base. Treat a handoff as context, not proof. Record the smallest requested
outcome and inspect uncommitted work before choosing a continuation.

Fetch the current base and head. Check whether newer code or another PR solved
the problem, changed its assumptions or removed the affected behavior. A clean
rebase is not proof the work remains useful. Continue or rework within the
authorized outcome. If obsolete, report concrete evidence rather than reviving it.
Closing the original PR, changing its base or replacing someone else's branch
requires existing authority.

Preserve authorship and verified co-author trailers when moving commits or
squashing. Credit contributors and link inherited work. Keep inherited commits
and corrective commits distinguishable when practical. Use resolving-merge-conflicts
for conflicts and git range-diff for rewritten series. Publish rewrites only
with an explicit lease on the observed remote head; reconcile a failed lease.

## File a reviewable PR

Check for an existing PR for the task branch before creating another. Inspect the
actual diff against its intended base. Follow repository title conventions.
Lead with the concrete problem and resulting behavior, then relevant proof and
limitations. Avoid an inventory of internal edits as the opening paragraph.
Rewrite stale titles and descriptions when scope changes.

Use a draft when required by source-only/no-deploy restrictions or unfinished
acceptance. Otherwise make the PR reviewable so required automation runs.
Link every created, taken-over or updated PR to the parent thread immediately.
Check public text and attachments for secrets/private context. Include
model/harness attribution when repository or user policy calls for it,
using verified identities rather than guesses.

## Handle findings without scope growth

Verify reviewer/bot findings against source and requirements before editing.
Track stable IDs and evidence. Fix in-scope defects; dispute incorrect findings
with a concrete reason and defer optional work explicitly. Do not relitigate
unchanged accepted behavior or launch reviews for style alone.

Post on the user's behalf only when the assignment or an invoked skill authorizes
it. Lead with the conclusion and cite code, checks or a reproduction. Distinguish
agent assessment from the user's words. Never invent an identity or model.
Verify the returned comment/review URL before resolving its thread. A failed
post is not a delivered explanation. Preserve unresolved requests.

## Deliver the checked revision

Use native PR watches and child completion, with one owner per dependency.
Before merging, fetch and inspect the live base, head, required checks, reviews
and mergeability. A later overlapping base change can invalidate earlier proof
even without a Git conflict. Reverify affected behavior.

Pin the merge to the checked head, for example gh pr merge with
--match-head-commit HEAD_SHA, using the repository's normal protected method.
If the head changed, reconcile and recheck. Never bypass protection.
On fleet guidance, merge can activate pull timers, so source-only or no-deploy
also excludes such a merge.

Full-stop leaves the PR unmerged and reports auto-merge/queue settings changed
to preserve that boundary. Only the owning parent watches. Unwatch at handoff,
question or explicit stop; cancellation overrides a late wake.
