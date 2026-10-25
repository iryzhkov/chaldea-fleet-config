# Mise tool ownership

The role never writes the user's global config. It reads literal TOML in
`~/.config/mise/config.toml`, `mise.toml`, `config.local.toml`,
`config.override.toml` and plain `conf.d/*.toml` fragments. Tools declared
there belong to the user: the role omits them from its managed drop-in and
from release lookups and installs. This applies to all versions and options,
including arrays, explicit pins and `allow_builds`. Unrelated tools,
environment values and settings remain byte-for-byte unchanged.

Mise reads fragments before `config.toml`, so the global file's version wins
during selection. That does not make duplicate declarations safe for every
command. With mise 2026.10.15, `mise use --global --dry-run codex@0.163.0`
rejects a tool declared in both global files and asks for `--path`.
The isolated regression confirms this collision and read precedence.
It does **not** reproduce the retained PC `mise latest` failure; that command
succeeds with the synthetic duplicate fixture. Agent-a's reported install
failure still lacks item-level stderr and has no established cause.

Before overwriting the old drop-in, the role parses TOML without evaluating
templates or printing values. A read-only `mise registry --json` call in an
empty temporary home identifies equivalent registry shorthands, aliases and
full backend identifiers. Thus `codex`, `aqua:openai/codex` and
`npm:@openai/codex` all relinquish fleet ownership of the same tool.
Tool-key options do not change ownership. The registry call neither loads
the user's config nor installs tools. Python 3.11+ and a compatible mise
with `registry --json` are required.

Malformed TOML, symlinked config files, non-tool sections in the managed file,
conf.d folders, includes, custom backend aliases/plugins, configuration
environment overrides and unknown shorthands fail before overwrite or installation. Resolve the reported
ownership ambiguity first; custom tools can use explicit backend identifiers.
This preflight is deliberately limited to the listed global sources. Project
config, environment-specific configs and environment overrides remain mise's
responsibility; the role does not migrate them or force `--path`.

Existing stale fleet declarations disappear on the next real converge.
An empty `mise_agents_tools: []` leaves an empty managed tools table and needs
no mise command. Custom selections use registered names or explicit backend
identifiers; each equivalent tool may be selected only once.
`mise_agents_install: false` still runs the read-only registry preflight for
a nonempty selection but performs no release lookup or installation.
Check mode reports the prospective drop-in without changing it or querying
or installing releases. Repeated real runs leave the drop-in unchanged.
For remaining fleet-owned tools, `mise_agents_minimum_release_age` still
filters the newest release, and `install_options` still goes only to install.

The CI fixture uses checksum-pinned mise 2026.10.15 in scratch and never
installs or invokes an agent CLI. It tests real duplicate detection and
selection, stale-file convergence, check mode, idempotence, aliases, options,
empty/custom selections and refusal before changes.
