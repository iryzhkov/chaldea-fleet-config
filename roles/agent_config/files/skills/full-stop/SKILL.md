---
name: full-stop
description: Complete a task to a verified PR ready for the user to merge when explicitly requested as a "full stop" workflow. Standalone stop or cancellation means stop working.
---

# Full stop workflow

Load full-send and follow its implementation, proof, independent review, PR and
CI workflow. An explicit request to do a task "full stop" authorizes that work
but reserves the merge for the user. Do not require a separate full-send request.
Mentioning or researching this skill does not invoke it.

Never merge, push to the default branch, enable auto-merge, enqueue a merge or
delegate those actions. For a PR this task owns, disable pre-existing auto-merge
and remove it from a merge queue before proceeding; verify again before pushing
and at handoff. Report auto-merge or queue settings changed. If that cannot be done, stop dependent mutations and report the
blocker. Do not modify an unrelated PR's settings.

Stop at full-send's gate with the PR open and unmerged. State whether it is ready,
waiting only for required human approval, or blocked, with the final head and
verification evidence. Unwatch before handing it back. If another actor merged
it, report that observed outcome rather than claim it remains unmerged.

A later "stop", "cancel" or "full stop" sent to halt active work is cancellation,
not permission to keep working toward a PR. Honor the user's intent and current
runtime lifecycle. Full-stop does not remove existing source-only or no-deploy
constraints or authorize deployment of unmerged changes.
