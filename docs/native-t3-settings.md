# Native T3 recovery settings

Fleet sets only `autoResumeLimitedThreads=true` in
`~/.t3/userdata/settings.json` for active T3 0.1.8 or later. The runtime floor
stays 0.1.6. omarchy-pc remains on 0.1.6 until the root operator upgrades it;
the settings task skips that version.

The role merges the key into the existing JSON object, preserves other keys,
mode, owner and group, and writes only when the value is not already true.
Missing settings files start with that one key and mode 0600. Invalid JSON
fails rather than replacing settings. The role never restarts T3.

Read-only inspection on agent-b on 2026-11-12 used the installed official
`~/.t3/runtime/versions/0.1.9/t3` executable. Its SHA-256 is
`2da70d7934fddbdd9b11ffc13d1bb390ac0b07181ac818941fa0b7b10efd0cee`,
also qualified in `jocasta:e341c5552d775da74640c460011595c2@18`.
The embedded official source has these paths and mechanisms:

- ServerConfig derives `settingsPath` as `userdata/settings.json`.
- `src/serverSettings.ts` starts a directory watcher for the settings path,
  debounces changes by 100 ms, and calls `revalidateAndEmit` to invalidate
  its settings cache, reload the file and publish changes.
- `UsageLimitRecoveryWorker` subscribes to `settings.streamChanges` and
  uses `preferences.autoResumeLimitedThreads` when selecting recovery work.
- Settings updates reload disk before merging a patch and persisting it.

This source inspection supports live reload without a restart. No host settings
were edited to test it, so this is not a live external-edit canary. There is no
supported CLI settings command. Stop rollout if live verification shows T3
ignores or overwrites the edit; do not add a reconciliation loop.

The same host's `t3 service --help` lists `restart`. Check running work and
recovery before `t3 service restart`, then wait for API readiness. The receipt
above proves one running turn continued exactly once and a pending question
survived on 0.1.9. It does not prove uninterrupted subprocess execution.
