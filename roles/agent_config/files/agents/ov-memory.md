# OV memory (shared agent instructions)

Maintained in chaldea-fleet-config's roles/agent_config/files/agents/ov-memory.md.
Keep it aligned with the ov-memory and ov-memory-curation skills in that role.
Edit those sources; installed copies are outputs.


# OV memory

Claude/Codex with registered native HTTP `ov` must use the native section of the
`ov-memory` skill, including its write/CAS, processing and maintenance limits.
Its dedicated personal tools require an explicit signed owner/action grant;
session capture and automatic commit are never implied.
OpenCode and other hosts retain legacy `ov-memory` where registered. Do not use
legacy procedures to bypass an HTTP refusal. The remaining reference describes
legacy stdio only; native curation uses the native skill section too.

An OpenViking store in the homelab (`https://ov.ryzhkov.dev`, through the edge
VIP), exposed by the `ov-memory` MCP server. It is memory for *agents*, not a chat log: durable facts
about infrastructure, decisions and projects.

## Search before you assume

Anything about the homelab, past setup work, or "how did we do this last time"
is likely already recorded. Search first, answer second. `memory_search` is
cheap; being confidently wrong about a machine you cannot see is not.

## The store's shape

Four scopes live under the root (`memory_ls "/"`):

| Scope | Holds | Writable here |
| --- | --- | --- |
| `viking://resources/` | Documents and per-project knowledge bases (`homeassistant`, `projects`, `cv-site`, …) | **yes** |
| `viking://user/` | Distilled memories about the user | no |
| `viking://agent/` | Per-agent instructions, memories, skills | no |
| `viking://session/` | Raw session transcripts | no |

## Documents are directories

OpenViking ingests a document as a *directory* named for the file, holding its
chunk files plus hidden `.abstract.md` / `.overview.md`. So
`viking://resources/projects/ov-agent-access.md` is a directory, not a file.

- `memory_read` walks that directory and returns the parts joined in document
  order, so a note reads back as one text however it was chunked. It never
  answers with an empty string for a node that has content: when a node really
  holds no text it says so and lists what it does hold.
- `memory_abstract` and `memory_overview` want the *directory*; a plain file has
  neither.
- Search hits are grouped by document, so a result names the note rather than one
  chunk inside it. Pass `group=False` to see the raw records.
- Notes under an `archive/` namespace are hidden from results; pass
  `include_archived=True` when the history is the point.

## Which tool

- `memory_search` — concepts and questions. First stop.
- `memory_find` — same, but also ranks stored resources; use when hunting for a
  document rather than a fact.
- `memory_grep` / `memory_glob` — exact strings and filename patterns, when you
  already know what you are looking for.
- `memory_tree` / `memory_ls` / `memory_overview` — orienting in an unfamiliar
  area before reading anything.
- `memory_abstract` — triage a search hit without paying for the whole file.
- `memory_read` — the full document, once you know you want it.
- `memory_stat` — how big a document is, and how many parts, before reading it.
- `memory_relations` — stored links, the `[[wikilinks]]` in a note, and the notes
  that link back to it.
- `memory_status` — when calls fail, before blaming the network.

Work top-down: search, triage abstracts, then read only what earns it.

Reorganising and repair belong to the [ov-memory-curation] skill: `memory_mv`,
`memory_rm`, `memory_reindex`, `memory_index_audit` and `memory_index_prune` all
change the store, so they are for a pass the user has asked for, not for normal
reading and writing.

## What goes where

`viking://resources/` is flat, one namespace per subject. As of 2026-08-29:
`asahi/`, `omarchy/`, `emby/`, `gaming-pc/`, `homeassistant/`, `cooking/`,
`cv-site/`, `personal-site/`, `openviking/`, `projects/` (holds `forever-home/`),
`iryzhkov/` (homelab-infrastructure, nvim-configuration, a Home Assistant
config dump) and `volcengine/` (an OpenViking source checkout).

- `memory_ls "viking://resources"` before writing. Reuse a namespace; create one
  only for a genuinely new subject, named for the subject in lowercase. Never
  leave content under an `upload_<uuid>` name -- nothing will find it later.
- **OV is the primary store.** Everything durable goes here: infrastructure,
  services, project knowledge, machine quirks, decisions and their reasons.
- **`~/.claude/projects/-home-igor/memory/`** is a cache of the subset that is
  about this laptop, kept because its `MEMORY.md` index loads automatically each
  session. A note that belongs there is written to *both* places.
- **The repo** holds what the code already says. Do not mirror it; point at it.
- Credentials: prefer a pointer ("key in the GNOME keyring, service=X") over the
  secret itself. Some older memories embed real credentials; do not add more.

## Writing

`memory_write` only, and only when the user asks for something to be remembered.
This store is curated on purpose: nothing is written automatically, so it stays
small enough to be worth searching.

- `to` must be under `viking://resources/`. The agent and user scopes are
  written solely by OpenViking's own session extraction, and `/resources`
  rejects writes elsewhere.
- Put the note in an existing namespace where one fits (`memory_ls
  "viking://resources"` to see them); create one with `memory_mkdir` only for a
  genuinely new area.
- Write the fact and *why it is true*, not the conversation around it. A note
  that will not make sense in six months is not worth storing.
- Indexing costs OpenAI embedding calls, so do not mirror things that live in a
  repo or in git history — link to them instead.
- The write is verified: it is read back and compared with what was sent, and the
  reply says so. A `WARNING` there means the stored text differs from what you
  wrote — keep the original in the conversation until that is understood.
- Superseding an existing note: write the new one, and store the old version with
  `archived=True`, which files it under `archive/` so it stops competing with the
  live note in search. Link related notes with `[[note-name]]`; those are resolved
  and recorded as real links on write.
- Ingestion reshapes long content. A Markdown note keeps every line, but its title
  becomes the name of the directory holding it and its sections come back in name
  order; a note written under another extension (`config.yaml`, `output.txt`)
  keeps every word but loses whitespace where the chunks were cut. For content
  that has to come back character-for-character -- configuration, command output,
  anything quoted -- pass `verbatim=True`, which stores it in parts that rejoin
  exactly.

## Machine-local memory is a cache of OV

`~/.claude/projects/-home-igor/memory/` holds this machine's own notes and loads
automatically each session. Its notes were mirrored into OV on 2026-08-29, so
the two stores now agree. Keep them agreeing: a new note about this laptop is
written to OV first and copied there second (with its one-line pointer added to
`MEMORY.md`); everything else lives in OV alone.

Do not treat the auto-loaded `MEMORY.md` index as the extent of what is known.
It is one line per laptop note, and OV holds far more, so search OV anyway.

---


# Curating OV memory

A maintenance pass, run on request. Normal reading and writing is the
[ov-memory] skill; this one is about the shape of the store as a whole.

## Moving and deleting are safe now

Both were once one-way doors, and older notes in this store still say so. As of
2026-09-05 the ov-mcp server repairs the index around them, so a real
reorganisation is an ordinary pass rather than a decision to escalate.

What the server actually does, and why the tools compensate:

- **`POST /fs/mv` half-updates the vector index.** It rewrites the records of the
  files it can list, but each document's hidden `.abstract.md` and
  `.overview.md` are filtered out of that listing, so their records keep pointing
  at the old URI, outrank the live note, and resolve to nothing. `memory_mv`
  prunes those orphans after every move and, by default, re-ingests the moved
  documents so their abstracts index at the new URI.
- **`DELETE /fs` removes the node before it cleans the index**, so it fails on a
  node that is already gone and cannot repair an orphan. `memory_index_prune`
  does that repair; `memory_index_audit "<query>"` finds the orphans by running
  the query, resolving every hit and reporting the ones with no node behind them,
  and `fix=True` prunes them.
- **`memory_rm` does clear the index** for the note it deletes, and also prunes
  the hidden records the server leaves behind. It takes `dry_run=True`; use it,
  because there is still no undo.
- **`memory_reindex`** rebuilds a note's chunks, abstract and index records from
  its current content. Use it when a note was moved with `reindex=False`, or when
  search returns a URI that no longer matches where the note lives.

The one cost to weigh: re-ingestion regenerates the abstract through the model,
so a move of a large namespace is not free. `memory_mv` skips re-ingestion above
twenty documents and says so.

## What a pass can do

1. **Audit, and report.** `memory_tree "viking://resources" level_limit=2` for
   the shape; `memory_overview` on anything unclear. Produce a findings list:
   duplicate subjects, `upload_<uuid>` names, namespaces holding one stray file,
   documents that have outgrown their subject.
2. **Check the index against the store.** Run `memory_index_audit` on the
   questions the store is supposed to answer. A hit that resolves to nothing is
   an orphaned record, and `fix=True` removes it.
3. **Reorganise.** `memory_mv` a badly named namespace or note, then confirm with
   `memory_index_audit` on a query the moved note should answer. Move a whole
   namespace in one call rather than note by note; each call re-ingests what it
   moved.
4. **Correct additively.** When a note is wrong or superseded, write the
   corrected note into the right namespace and say in its text which URI it
   supersedes. `memory_write(..., archived=True)` files the old version under
   `archive/`, where it stops competing with the live note in search.
5. **Delete what is genuinely dead**, with `dry_run=True` first, and only what the
   user has agreed to lose. There is no undo.
6. **Leave a decision list.** End the pass with what could not be fixed and what
   it would cost, rather than half-applying a reorganisation.

## Known drift (as of 2026-09-05)

- `resources/homeassistant` and `resources/iryzhkov/homeassistant` are two
  namespaces for one subject.
- `resources/iryzhkov/*` nests three subjects under a username.
- `resources/projects/*` mixes with top-level project namespaces.

Fixed on 2026-09-05, and left here as a record of what these tools now handle:
the cooking guide that sat under `resources/upload_864a4583ab504fe2ab2f688df6c17977`
left an orphaned abstract record behind when it was moved, which ranked first for
cooking questions and read as empty; `memory_index_prune` removed it, and an audit
across fourteen subject queries found no other orphan in the store.

`memory_relations` no longer returns `[]` for a note with `[[wikilinks]]`: the
links are parsed and resolved by ov-mcp, and recorded in OpenViking as real links
when a note is written.
