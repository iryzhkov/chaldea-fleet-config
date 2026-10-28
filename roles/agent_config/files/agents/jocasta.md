# Jocasta: shared working documents

Maintained in chaldea-fleet-config's roles/agent_config/files/agents/jocasta.md.
Edit that source; installed copies are outputs.

Use registered Jocasta WebMCP tools for shared plans, handoffs, research and prompts.
Ordinary interactive and ordinary delegated T3 threads using the managed interactive
identity have document access across projects. Protected Chaldea profiles retain
their explicitly granted read-only project access. Delegation alone does not
determine an identity or permission. Use the tools exposed to the current profile;
never bypass a denial through another identity.

## Find and read

- Use `search` with `q` and optional `project`, or `list` with a bounded
  `prefix`. Search is lexical; a bounded result is not proof of absence.
- Use `get` with an exact `id` or `path`. Keep
  `jocasta:DOCUMENT_ID@REVISION` references in handoffs.
- `get` with `view: "outline"` returns headings, line ranges and the revision;
  `levels` narrows heading depth. Use `section: {heading, heading_line}` for an
  exact section or `lines` for a bounded range. Pin `revision` to read the same
  snapshot. Duplicate headings require `heading_line`.
- `search` with `include_excerpts` returns bounded excerpts of the exact revision.
  Read the located passage before choosing an edit.
- Use `history` for revision metadata and grant-bound pagination. Compare versions
  through two revision-pinned `get` calls; rendering a diff is a client task.
  For presence, `get` with an outline avoids returning the body; `not_found` can
  mean absent or inaccessible, not unrestricted absence.
- Save returned content in owned scratch when a file artifact is needed.
  Repository source remains in Git and uses Huyang.

## Change documents safely

Every mutation requires a fresh `idempotency_key`. Reuse a key only for an identical
request after an uncertain response; changed requests need new keys. The server's
actual schema is authoritative.

- Create with `mutate`, `operation: "create"`, an exact project path and content.
- Change one passage with `edit`: exact ID or path, observed `if_revision`,
  unique nonempty `old`, `new`, optionally an exact `section`. Zero or multiple
  matches and stale revisions refuse without a change. Reread and reconcile.
- Before whole-document `mutate` with `operation: "put"`, fetch the FULL current
  document, reconcile and pass its `if_revision`. Never write a section or
  line-range response back as the whole document.
- `mutate` also supports `move` with `destination`, `archive`, `unarchive`
  and `restore` with `source_revision`. Read the full current document and guard
  these changes with its `if_revision`. Restore preserves revision history.
- Never guess a mutation target from search or overwrite a newer revision to evade
  a conflict. Remaining CLI/REST/MCP consumers share these revision rules.

Keep working documents current rather than append-only. Replace obsolete active
state and retain an exact prior revision or durable receipt before removing evidence.
Keep decisions in the plan, current task/run state in the checkpoint and details in
linked receipts. Fetch the whole document for a safe update but print only relevant
parts. Use normal spacing. Roadmap-executor owns checkpoint shape; this adds no report.

Documents inactive for 30 days archive automatically, remain retrievable/searchable
with history, and reads reset inactivity without unarchiving. Do not mirror working
documents into OV. If Jocasta is unavailable, report it rather than silently creating
mutable copies elsewhere.

## Authentication and availability

Use the existing managed native registration and its private short-lived headers.
Never run its headers helper as a model-visible command or print credentials,
headers or auth caches. Never copy human/native auth caches. Reconcile a managed
enrollment failure with its owner; do not request another browser login merely
because an already-enrolled helper failed. Only an explicitly selected public OAuth
registration uses that client's supported login flow.

WebMCP is the normal agent path. Do not install or use the legacy CLI to escape an
unavailable tool, restriction or grant. Offline import and operator recovery retain
their separately approved procedures until migrated; they grant no broader runtime
access. Preserve credentials required by remaining consumers during retirement.
Registration, installed configuration and actual native acceptance are separate evidence.
