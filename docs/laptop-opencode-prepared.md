# Laptop OpenCode selection

The laptop's `inventory/host_vars/laptop/chaldea-jocasta-tooling.yml` selects
the `jocasta-tooling-opencode` preset, enrollment and profile beside its
existing Claude and Codex entries. The entries are the reviewed prepared
selection, copied unchanged: same tooling project, workspace, destination,
`get`/`history`/`list`/`search` read grant, 1800-second ceiling and
`delegate: false`. No grant, ceiling or validator is widened. Every other host
is unchanged.

This is source only. Merging it activates the selection through the laptop's
ordinary pull, so root merges it only after its native acceptance passes. The
source carries no account, secret, provider instance or native process; the
role stats the operator-provisioned private files and stops the pull if one is
missing or unsafe.

The model is `opencode/big-pickle` with no model options. Root's pinned 2.1.3
public-source extract contains big-pickle and lacks beam-free; the live T3
catalog lists big-pickle with no options. Native model availability and
provider authentication in the private HOME are part of root's acceptance.
The existing session-policy parser accepts a slash in the model string; the
OpenCode profile has no model field.

Root owns these gates before merging:

- Stage the separately verified client-v0.4.20 runtime. Archive SHA-256
  `ed3376ab8f21c1b6bb7b2d03e9e8c074dd43ed25be4881aafe574a12e8b618ff`,
  manifest SHA-256
  `c8542918859a19ec99065117c5bd359a12de1838d6f54a4090f5e1ee12a2d2d1`.
  The source pin already selects that runtime. Installed waits stays on
  client-v0.4.18 until root activates it. The pull admits the installed
  client-v0.4.18 system unit only by its exact rendering, replaces it with the
  client-v0.4.20 unit and restarts waits through the normal guards; any other
  unit is refused before writes. A missing runtime stops convergence; the PR
  itself grants no deployment authority.
- Stage the exact public arm64 OpenCode 2.1.3 native at the profile's
  canonical asset path with its reviewed hash and size. Ordinary installed
  OpenCode is 2.1.4 and stays unchanged; its moving installation is not this
  protected native. Provision the distinct private 0700 HOME and tmpdir, then
  qualify the model and authentication there. Never copy the ordinary
  OpenCode login or inspect it as part of source validation.
- Enroll the ordinary account `chaldea-laptop-jocasta-tooling-opencode`
  through the existing enrollment path and deliver its app password at the
  named protected secretFile. YAML names an account and secret path; it does
  not create either.
- Register only `opencode-jocasta-tooling` with binaryPath
  `/etc/chaldea/sessions/jocasta-tooling-opencode/exec`. Keep ordinary
  OpenCode and the deployed Codex/Claude providers intact.
- Pass the standard native checks for this exact source: an actual tooling
  read and other-project denial, exact service, helper and provider identity,
  stored result, status and completion, and cleanup. Do not replay a call
  automatically.

Broader denied dispatch, including injected T3 tools, and real in-flight
renewal or reconnect during an MCP call remain unqualified after that
acceptance. The accepted pinned-native fixtures are separate evidence for
their exact bytes and scenarios only.

The instance policy uses OPENCODE_CONFIG_DIR; no global /etc/opencode policy
is introduced. The existing per-serve foreground supervisor owns renewal and
cleanup. It writes a watched atomic 0600 header inside a private 0700 launch
directory and binds every renewal to the original session, run and absolute
deadline. It schedules at token expiry minus 25 seconds, stops on first refusal,
and never retries, replaces the admission or extends its ceiling. Process-group
signaling and parent-death handling remain per serve. The launcher adopts and
reaps orphaned descendants, signals its owned group after direct-child exit,
and escalates survivors through pidfds after three seconds, with a further
three-second cleanup bound. A helper result arriving after timeout, original
deadline or the old header's stop margin is refused before publication. An uncatchable launcher death can leave the private launch
directory until operator cleanup; an issued JWT expires independently.

The retained credential-free native atomic-rename proof and policy fixtures
remain evidence only for their exact bytes and scenarios. They do not qualify
auth, actual denied dispatch, arm64 model execution or mid-call reconnect.
The earlier startup-exploit inference is rejected: the native prompt path
activates policies. Keep actual dispatch acceptance as a separate gate.

This change does not alter ordinary client/current/previous, quota, collector,
Node 26.10 rollback or the laptop's mise-prune-off setting. It adds no other-host
OpenCode rollout, HoloNet action, fork, standalone refresher or daemon.
