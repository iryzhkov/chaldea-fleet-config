# Ordinary OpenCode and the managed Jocasta helper

This capability lets ordinary interactive OpenCode on laptop, agent-a, agent-b
and omarchy-pc (GamingPC) use full Jocasta through the existing managed
identity, the existing per-host enrollment and the existing fixed helper
command `/usr/local/libexec/webmcp-interactive-headers jocasta HOST`. It adds
no identity, credential, token store, bearer file, daemon, wrapper, service,
grant or lifetime. The helper, its compiled contract and signature checks, and
the Claude and Codex registrations are unchanged. Limited Chaldea tooling
profiles, including the limited OpenCode profile, are unchanged and separate.

The capability is off. No inventory selects it. Root selects it per host after
that host's protected staging and native qualification.

## Mechanism

OpenCode 2.1.4 has no header-helper field. Its supported PromisePlugin API
exposes a synchronous MCP transform and an asynchronous reload. Fleet installs
one plugin, rendered from
`roles/webmcp_interactive/templates/opencode-webmcp-jocasta.js.j2`, at exactly
`~/.config/opencode/plugins/webmcp-jocasta.js`. OpenCode auto-discovers
standalone `.js` files in the global config directory's `plugins` directory.

The plugin, in each OpenCode location (working directory) separately:

1. Refuses unless all of these hold: OpenCode reports exactly 2.1.4; the
   rendered host is one of the four canonical names; the process UID equals
   the rendered UID; `HOME` equals the rendered home; `OPENCODE_CONFIG_DIR` is
   unset; `XDG_CONFIG_HOME` is unset or the rendered home's `.config`; and the
   module's real path is the rendered home's plugin path. Refusal registers
   nothing and never runs the helper. The host comes only from the rendered
   declaration; the environment can only cause a refusal.
2. Registers one transform. A rebuild starts from fresh configuration, and
   OpenCode applies configured servers before external plugins, so any
   `jocasta` entry the transform sees belongs to the user's config or another
   plugin. Such an entry is left exactly as it is and no token is minted. The
   transform never throws, because a throw would disable the plugin group.
3. Once the transform has observed configuration and no foreign entry exists,
   runs the helper with `shell: false`, the fixed argv `jocasta HOST`, `cwd`
   `/`, the environment `PATH=/usr/bin:/bin` only, stdin and stderr ignored,
   a 12-second kill bound (the helper has its own 8-second deadline) and a
   16 KiB stdout bound.
4. Accepts only the helper's exact one-line output
   `{"Authorization":"Bearer <compact JWT>"}` followed by a newline. Anything
   else, a nonzero exit, a signal or a spawn failure is a failure.
5. Keeps the header only in its closure and, through `editor.set`, in native
   MCP memory as `{type: "remote", url: "https://jocasta.mcp.ryzhkov.dev/mcp",
   oauth: false, headers: {Authorization}}`, then calls `ctx.mcp.reload()`.
   OpenCode reconnects the changed server; other servers are untouched.

No value is logged. The plugin has no console output and writes no file. No
model-visible tool, command or MCP surface can invoke the helper, and the
plugin adds no administrative server. OpenCode JSON never receives a bearer.

## Expiry and refresh

The helper's contract: each call mints a new token (no cache); a token is
issued only with more than 30 seconds and at most 300 seconds left. The plugin
reads the `exp` claim of this already verified output only to end its use
earlier: validity is `min(exp, close + 300s)`, and output with 20 seconds or
less left is refused. This adds no trust decision and exposes no claim.

- Deadline: validity minus 10 seconds. Each held token has its own expiry
  timer, independent of the refresh loop, so a refresh helper that hangs (up
  to its 12-second bound) cannot extend it. At the deadline that timer drops
  the token and calls `ctx.mcp.reload()`, which removes the entry and its
  connection. A replacement token cancels the old timer, and an old timer can
  only drop the token it was armed for. The transform also withholds a token
  at or past its deadline on any rebuild, even if a timer was late.
- If that reload fails, the token is still dropped and any later rebuild
  withholds it, but the native connection keeps its old header until a
  rebuild happens. Local removal is never server revocation: an issued token
  stays valid at Jocasta until its own expiry, at most 300 seconds.
- Refresh: at half the time to the deadline (about 145 seconds for a
  300-second token).
- Failure: a still-valid token stays only until its deadline. Retries run
  every 15 seconds, clamped to the deadline. At the deadline the token is
  dropped and the entry disappears; retries continue every 15 seconds.
- Collision: no token is minted while a foreign `jocasta` entry exists; a
  held token is dropped.

Cleanup (location or process shutdown, plugin reload) stops scheduling,
clears its refresh and expiry timers, sends SIGTERM to an in-flight helper, waits up to 2 seconds,
then SIGKILL and waits for exit. It then disposes only its own transform.
Timers are unref'd.

A refresh reconnects Jocasta, so a tool call in flight at that instant may
fail and need a retry. A header already issued stays valid at the server until
its own expiry; ending issuance is not revocation.

## Limited profile boundary

The limited OpenCode launcher gives its child a private `HOME`, matching XDG
directories, a private `OPENCODE_CONFIG_DIR` and project configuration
disabled. OpenCode's global plugin directory is then the private config
directory, so the ordinary `~/.config/opencode/plugins` file is not discovered,
even with the working directory `/home/igor`. A copy placed anywhere else fails
the module path, `HOME` and `OPENCODE_CONFIG_DIR` checks before the helper.
These controls prevent accidental cross-use. They do not sandbox code running
as the same Unix user, which can run the helper directly.

## Selection, custody and rollback

`webmcp_interactive_opencode_state` (default empty) is read by
`mcp_registrations`; when nonempty it includes
`roles/webmcp_interactive/tasks/opencode.yml` after managed staging:

- `present` requires `webmcp_interactive_enabled` and, except on laptop,
  `webmcp_interactive_laptop_qualified`. It renders the plugin with this host's
  `inventory_hostname`, `ansible_facts.user_uid` and `fleet_home`, which must
  equal `ansible_facts.user_dir`. Laptop renders UID 1001 and the other hosts
  1000 from their own facts; every account keeps its own enrollment.
- `absent` removes only a file that starts with
  `// fleet-managed: webmcp-jocasta/v1`. It works with managed mode disabled.

Both refuse symlinks, wrong types, foreign owners, group- or world-writable
components, a hard-linked plugin and an unmarked file at the plugin name, and
leave them untouched. Neither touches OpenCode JSON, the Huyang plugin, other
plugins, the enrollment or the helper. A repeat run is a no-op. In check mode a
fresh destination is reported and not created.

To activate a host, root adds to that host's own inventory, after its managed
staging is in place and native qualification has passed:

    webmcp_interactive_opencode_state: present

Rollback sets `absent` on that host (or removes the selection after an
`absent` pull). Remove this consumer before deleting the staged enrollment or
helper. A running OpenCode keeps its in-memory registration until that process
or location ends. Rollback never deletes user files or clears OpenCode caches.

A future OpenCode version is refused until this plugin and its contract tests
are reviewed for it; the ordinary OpenCode wrapper is not pinned.

## Evidence and remaining native checks

`tests/test_webmcp_opencode.py` renders the template through the role in a
scratch home and runs `tests/webmcp-jocasta-plugin.test.mjs` against the
rendered file with fake helper processes, clock and editor. A separate scratch
fixture ran the exact template with OpenCode 2.1.4 natively; its receipt is
root's evidence and not committed here. Fixtures are not host acceptance.
Each host still needs its own native check with the real enrollment and helper:
activation, full Jocasta read/write, a refresh past one token lifetime, and
rollback.
