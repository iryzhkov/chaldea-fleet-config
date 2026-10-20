# Jocasta: shared working documents

Maintained in chaldea-fleet-config's roles/agent_config/files/agents/jocasta.md.
Edit that source; installed copies are outputs.


Jocasta stores shared plans, handoffs, research and prompts. Use its CLI on any fleet host:
`jocasta search 'rough plan name' --json`, then `jocasta get PROJECT/plans/FILE.md --output
~/.cache/roadmap-work/plan.md --json`. Search is lexical, so a bounded search is not proof of absence. Use exact
`jocasta:DOCUMENT_ID@REVISION` references in handoffs.

Create with `jocasta put PROJECT/handoffs/FILE.md --file ~/.cache/roadmap-work/handoff.md --create`. For updates,
fetch the full document, reconcile changes, and use `--if-revision N`. Never write back a
partial line range, guess a mutation target from search, or retry a conflict by replacing the
newer revision.

Keep working documents current rather than append-only. Replace obsolete active/pending
state when reconciling; do not leave contradictory stage summaries below a new update.
Before removing detail still needed as evidence, retain an exact revision link or durable
receipt. Jocasta revisions preserve history; do not duplicate it in every plan, checkpoint
and handoff. Keep the plan's decisions and strategy separate from checkpoint task/run state.
Fetch the whole document for a safe update, then inspect and print only the operative parts
needed for the decision. Use readable sentences and normal spacing. Roadmap-executor owns
the operative checkpoint shape and soft size target; this guidance adds no new report.

Jocasta is the shared working-document store: repository source stays in Git and is read and
edited through Huyang and OV stays curated long-term memory.
Do not automatically mirror working documents into OV. If Jocasta is unavailable, report the
failure rather than writing mutable copies elsewhere. Documents are archived automatically after
30 days without a read or update, remain searchable and retrievable, and keep their history.

Credentials are per-host and must not be copied into prompts, logs, source or handoffs.


