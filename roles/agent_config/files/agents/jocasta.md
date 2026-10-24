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

## Web MCP

Where the `jocasta` MCP server is registered (the laptop's ordinary interactive Claude
and Codex sessions), it reads and changes the same documents and revisions as the CLI
and REST API, through your own native OAuth login. If it reports that
authentication is needed, ask Igor to complete that client's MCP login; never copy a
token into a prompt, config or command. Protected Chaldea tooling sessions keep their
read-only tooling access and do not get this server. The server's tool schemas are
authoritative; if a field below differs, follow the schema.

- Read narrowly. `get` with `view: "outline"` lists headings with their line ranges and
  the revision; `get` with `section: {heading, heading_line}` returns one exact section,
  and `lines` a pinned range. Pass `revision` to keep reading the same snapshot. A
  heading that occurs more than once is refused as ambiguous; add `heading_line`.
- `search` with `include_excerpts` returns bounded excerpts of the exact returned
  revision. An excerpt locates text; read it before choosing an edit target.
- Change a passage with `edit`: exact path or ID, `if_revision` equal to the revision you
  read, nonempty `old` text that occurs exactly once (optionally within one `section`),
  `new`, and a fresh `idempotency_key`. Zero or several matches and stale revisions are
  refused without a change; re-read, reconcile and retry with a new key. Reuse a key
  only to retry the identical request.
- Whole-document writes (`mutate` put) and create, move, archive, unarchive and restore
  follow the update rules above: fetch the full current document, reconcile and pass
  `if_revision`. A targeted `edit` is the only partial write.
- CLI, REST and Web MCP may be mixed; every write needs the latest revision, whichever
  path made it.


