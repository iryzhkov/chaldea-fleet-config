# Jocasta: shared working documents

Generated from the Working documents: Jocasta section of omarchy-setup's
config/claude/CLAUDE.md. Edit it there and run agents-instructions-gen.


Jocasta stores shared plans, handoffs, research and prompts. Use its CLI on any fleet host:
`jocasta search 'rough plan name' --json`, then `jocasta get PROJECT/plans/FILE.md --output
/tmp/plan.md --json`. Search is lexical, so a bounded search is not proof of absence. Use exact
`jocasta:DOCUMENT_ID@REVISION` references in handoffs.

Create with `jocasta put PROJECT/handoffs/FILE.md --file /tmp/handoff.md --create`. For updates,
fetch the full document, reconcile changes, and use `--if-revision N`. Never write back a
partial line range, guess a mutation target from search, or retry a conflict by replacing the
newer revision.

Jocasta is the shared working-document store: repository source stays in Git and is read and
edited through Huyang and OV stays curated long-term memory.
Do not automatically mirror working documents into OV. If Jocasta is unavailable, report the
failure rather than writing mutable copies elsewhere. Documents are archived automatically after
30 days without a read or update, remain searchable and retrievable, and keep their history.

Credentials are per-host and must not be copied into prompts, logs, source or handoffs.


