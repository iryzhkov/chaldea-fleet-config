# Preserved bootstrap utilities

Canonical agent-tooling sources moved from iryzhkov/omarchy-setup main
4d8529a to iryzhkov/chaldea-fleet-config on 2026-10-18 by Igor's decision.
The original paths below this directory are retained byte-for-byte.

This directory preserves the laptop worker setup and isolation examples,
agent-scratch-reap script and user units, Claude settings, and the third-party
skills source list. Supporting tests and the laptop isolation document are
included for reference. Their old paths and bootstrap assumptions are historical.

These files are source-only. No fleet role installs, invokes, enables or removes
them. Existing host installations keep running as before. Reworking their
installation or retiring installed units needs a separate reviewed change.
The old sandbox CI contract was retired with its Omarchy workflow.

Current shared instructions, skills and references live in
roles/agent_config/files/. The direct maintained sources replace the obsolete
Omarchy instruction generator and Steward policy projection. The old
implementation-session and publish-agent-tooling skills are superseded by
fleet's roadmap-executor, review-delegation and Chaldea workflows.
