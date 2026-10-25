# Prepared laptop OpenCode selection

The driver is available in source. The laptop's active inventory still selects only
its existing Codex and Claude profiles. The public fragment
[examples/laptop-jocasta-tooling-opencode.yml](examples/laptop-jocasta-tooling-opencode.yml)
is outside inventory and no playbook or role loads it. Its keys deliberately differ
from role inputs. Passing it as extra vars does not select OpenCode.

After root's acceptance, merge its `presets`, `enrollments` and `profiles` entries
into the corresponding laptop `chaldea_client_session_*` maps. Preserve every
existing entry, ceiling, destination, tooling project/workspace and read grant.
This is a future source activation change, not a command to run now. No account,
secret, private directory, provider instance or native process is created by
the fragment.

The prospective model is `opencode/big-pickle` with no model options. Root's
pinned 2.1.3 public-source extract contains big-pickle and lacks beam-free;
the live T3 catalog lists big-pickle with no options. This selection remains
acceptance input only. Native model availability and provider authentication
in the private HOME are unqualified.
The existing session-policy parser accepts a slash in the model string; the
OpenCode profile has no model field. No validator is loosened for this selection.

Root owns these gates before activation:

- Stage the separately verified client-v0.4.20 archive before merging this
  branch into the active laptop pull path. Archive SHA-256
  `ed3376ab8f21c1b6bb7b2d03e9e8c074dd43ed25be4881aafe574a12e8b618ff`,
  manifest SHA-256
  `c8542918859a19ec99065117c5bd359a12de1838d6f54a4090f5e1ee12a2d2d1`.
  The source pin already selects that runtime. Installed waits remains
  client-v0.4.18 until root stages and activates it. Missing runtime stops
  convergence; the draft PR itself grants no deployment authority.
- Recover and stage the exact public arm64 OpenCode 2.1.3 artifact at the
  fragment's canonical asset path with its reviewed hash. Ordinary installed
  OpenCode is 2.1.4 and stays unchanged; its moving installation is not this
  protected candidate. No isolated auth HOME exists yet. Provision the distinct
  0700 HOME and runtime directory, then qualify the model and authentication
  there. Never copy the ordinary OpenCode login or inspect it as part of
  source validation.
- Enroll the prospective ordinary account
  `chaldea-laptop-jocasta-tooling-opencode` through the existing enrollment
  path and deliver its app password at the named protected secretFile.
  YAML names an account and secret path; it does not create either.
- Register only `opencode-jocasta-tooling` with binaryPath
  `/etc/chaldea/sessions/jocasta-tooling-opencode/exec`. Keep ordinary
  OpenCode and the deployed Codex/Claude providers intact.
- Qualify an actual native T3 session, the real helper/service binding,
  allowed and denied tool dispatch including injected T3 tools, and reconnect
  during an in-flight MCP call. Do not replay a call automatically.

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
