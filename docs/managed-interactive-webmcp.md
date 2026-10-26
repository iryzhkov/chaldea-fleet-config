# Managed interactive Jocasta capability

Laptop acceptance and persistence are the base for this candidate. Its inventory,
ARM helper pin and protected tooling profiles remain unchanged. This source adds
explicit managed selections for agent-a, agent-b and omarchy-pc/GamingPC.
These registrations cover Claude and Codex. Ordinary OpenCode uses the same
helper through a separate, default-off plugin selection described in
[the OpenCode consumer](opencode-interactive-jocasta.md). These three hosts still need protected staging and actual
on-host Codex AND Claude qualification, CAS, idempotency and >330s reuse checks.
This source is no acceptance receipt. Root owns enrollment, guarded source
delivery, review/CI, activation and acceptance. Keep this candidate off main
until root qualifies that exact source and the staging prerequisites.

All four host selections use the installed helper at its shared architecture
SHA256 and {{ fleet_home }}/.config/webmcp-interactive/enrollment.json as their
own local protected sources. The existing role validates custody and retains
exact bytes on a repeat pull. No controller staging path or private digest is
committed. The laptop's public OAuth registration remains its disabled-mode
fallback; the three new hosts previously had no interactive Jocasta entry.
Role defaults stay off. Each new host explicitly records laptop qualification.
The operator procedure is in [the three-host staging brief](managed-interactive-three-hosts.md).
An explicit Jocasta state=absent is honored even while managed mode is enabled;
remove the native consumers, including an OpenCode plugin selection, before
deleting its staged credential/helper files.

Before activation, account for Codex's native credential precedence. A stored
Jocasta OAuth login can override helper Authorization. If actual connection
behavior selects that credential, use only supported codex mcp logout jocasta,
then reconnect and verify helper-backed use. Do not inspect or clear unrelated
native credentials, and do not treat the earlier canceled login as proof of a
stored Jocasta credential.

## Closed native helper

Build tools/webmcp-interactive-headers with Go on an isolated job host.
The installed command is exactly:

    /usr/local/libexec/webmcp-interactive-headers jocasta HOST

HOST is one of the four inventory names, including omarchy-pc, not gaming-pc.
The helper resolves the actual OS account home, ignoring HOME for credential
selection. It reads only .config/webmcp-interactive/enrollment.json there.
It rejects symlink ancestors/leaf, shared-writable or foreign ancestors, a
nonprivate final directory, and anything except this UID's single-link 0600
regular file of at most 4096 bytes. Root or this UID may own safe ancestors.

The service contract is compiled in: HTTPS auth.ryzhkov.dev/application/o/token/,
issuer .../application/o/jocasta-managed-interactive/, its exact jwks/ endpoint,
client jocasta-managed-interactive, resource
https://jocasta.mcp.ryzhkov.dev/mcp and scopes jocasta.read jocasta.write.
There is no endpoint, issuer, scope, credential path or secret CLI/env option.
The request uses username plus app password and client_credentials, without a
client secret, assertion, offline scope or refresh grant.

Network trust uses Go's system HTTPS root loading, including Go's standard CA
environment overrides. Proxy environment settings are ignored. Never supply
untrusted CA overrides to the native client/helper. Redirects are refused.
The entire exchange/JWKS operation has an eight-second deadline, bounded headers
and 32KiB token/64KiB JWKS bodies. No error response body is read or logged.
The helper verifies an actual RS256 signature with a matching bounded RSA JWK
from the pinned HTTPS JWKS. It then checks exact issuer/resource/client/scopes,
jocasta_operator=true, signed webmcp_identity matching this host's username,
nonempty subject, absent jocasta_projects, lifetime <=300s and >30s reserve.
A decoded token alone is never trusted. No key/token/credential cache is written.
The only successful stdout is native header JSON. All failures print one generic
line without server responses or credential values.

Codex receives http_headers_helper; Claude receives headersHelper. Ordinary
OpenCode has no helper field; its fleet plugin runs the same fixed command in
memory only (opencode-interactive-jocasta.md). The registration
module's auth_mode=managed_helper accepts only this fixed name, URL, command and
approved host, or the separate laptop OV tuple below. extra must be empty. Public auth_mode=oauth retains its existing
refusal of arbitrary helpers, headers, bearer values and client secrets.
Unrelated native entries are preserved. Limited Codex profiles disable jocasta;
strict Claude tooling config remains independent. Chaldea session admission and
runtimes are unchanged.

## Protected delivery and future root procedure

The infra playbook authentik-webmcp-interactive.yml uses the existing encrypted
controller API credential and stages a per-host private JSON enrollment beside
its protected receipt. Fleet takes that output, never the administrative token.
No credential value belongs in argv, environment, inventory, logs or diffs.
The input has exactly version=1, owner UUID, host, username,
password and generation. The private controller directory must already be owned
by the controller UID, mode 0700, under safe nonlinked ancestors; file mode 0600
and one link. The private lookup validates custody through held directory FDs.

Fleet inputs for the initial authorized host delivery are:
webmcp_interactive_enabled=true, webmcp_interactive_helper_source as an absolute
reviewed native binary path, webmcp_interactive_helper_sha256, and
webmcp_interactive_credential_source as the protected infra output path.
Use a private 0600 extra-vars file, never inline credential values. Root runs
site.yml only on the selected actual host with --tags mcp_registrations.
This converges the role's normal existing MCP registrations too; root must
inspect its check/diff and bound that ordinary convergence.

For rotation, provide the exact prior credential-file SHA256 privately as
webmcp_interactive_previous_credential_sha256. A present destination must match
the current input or that explicit prior digest. Foreign files and unexplained
replacement are refused. Helper upgrades likewise require the exact reviewed
previous public helper SHA256. Credentials are copied with no_log/diff=false,
0600, no backup. The helper is root-owned 0755 at its fixed path.

Root must persist each accepted host's opt-in in owning host inventory so an
active pull does not restore its former public OAuth registration. After initial
delivery, local pull inputs may use the installed helper and enrollment as their
own protected sources, with the reviewed public binary SHA256. Do not commit
controller paths or secret digests as portable fleet defaults. Keep all other
hosts disabled until laptop acceptance, including a repeat pull/no-op check.

Example future root invocation, from this repository on the selected host:

    ansible-playbook -i inventory/hosts.yml site.yml --limit laptop \
      --tags mcp_registrations --check --diff --extra-vars @/PRIVATE/fleet-laptop.yml
    ansible-playbook -i inventory/hosts.yml site.yml --limit laptop \
      --tags mcp_registrations --extra-vars @/PRIVATE/fleet-laptop.yml

These are instructions, not commands executed by this source change. Root
qualifies the actual installed versions at each host's acceptance boundary.
Earlier helper and host-version observations are historical. Fixtures do not
qualify any official T3 path.

Persistent rollback restores only the affected host's prior fleet selection.
A backend verifier rollback requires root's separate coordinated infra decision;
retain the accepted laptop and existing backend during this three-host slice.
Restore only the affected host's owned native entries. Root coordinates any
separate verifier change because infra has one operator-verifier slot.
Revoke issuance through the receipt-bound procedure and remove only owned helper/enrollment files after
proving no remaining consumers. Setting enabled=false alone does not delete files.
The reverted laptop selection lets ordinary pulls retain public OAuth; other
hosts' prior entry absence requires explicit state=absent. Never clear client caches.
If a stored Jocasta OAuth credential takes precedence in Codex, root may need the
supported per-server logout only after inspecting that concrete condition.
Never use global logout or copy unrelated authentication.

Another Web MCP service needs a separately reviewed explicit application
policy/resource/scope grant and registration/helper capability. Adding a URL
creates no grant. This helper supports exactly Jocasta on the four hosts and
OV for laptop Codex, below. These controls do not isolate secrets from
arbitrary code running as the owning Unix user.

## Laptop OV for ordinary Codex

The second closed helper tuple is exactly:

    /usr/local/libexec/webmcp-interactive-headers ov laptop

It lets ordinary interactive Codex on the laptop read the existing OV HTTPS
MCP endpoint https://ov.mcp.ryzhkov.dev/mcp with a short-lived token, without
a browser or model login. Its identity is separate from the Jocasta managed
identity and from the limited Chaldea preset ov-tooling-codex. homelab-infra's
playbooks/authentik-ov-http-identities.yml enrolls the account
chaldea-laptop-ov-interactive-codex under the same existing owned OV
application and delivers its raw app password to the bound laptop UID at
~/.config/chaldea/authentik/ov-interactive-codex.app-password. Fleet never
receives, reads, copies or checksums that credential.

The helper finds the file from the account database's home for its UID,
ignoring HOME and every other environment value. It applies the same held
no-follow directory walk as for Jocasta and accepts only this UID's
single-link 0600 regular file of 16 to 256 printable ASCII bytes, without a
newline, in a 0700 directory. It never opens the limited preset's
ov-tooling-codex file.

The compiled contract is: token endpoint auth.ryzhkov.dev/application/o/token/;
client ov-http-a63e197f-machine; username chaldea-laptop-ov-interactive-codex;
scope ov.read; issuer .../application/o/ov-http-a63e197f/ and its exact jwks/
endpoint. The request follows Chaldea's established OV session exchange,
without a resource indicator, because the OV scope mapping fixes the audience.
The response must be a Bearer token with scope exactly ov.read, 30 < expires_in
<= 300 and no refresh token. After RS256 verification against the pinned JWKS,
the helper requires the OV verifier's own rules (ov-mcp ov_http/auth.py): a
header of only alg, kid and typ, kid in [A-Za-z0-9_.-]{1,128}, typ JWT or
at+jwt when present, at most 32 claims and a token of at most 12288 bytes. It
then requires the exact issuer, a single string audience equal to the OV
resource, azp equal to the client, scope exactly ov.read, ov_namespaces exactly
[viking://resources/homeassistant-api/rest-api.md], integer iat/exp with the
same lifetime and reserve rules as Jocasta, and a nonempty subject of at most
256 characters without control characters. It refuses every other service's
grant claim, the Jocasta operator and identity claims, any ov_actions claim,
and case-folded aliases of any checked claim.

The OV scope mapping signs no account identity, so unlike the Jocasta mode the
helper cannot compare a signed identity claim with its username. The subject
is Authentik's opaque per-user value, checked for shape only, exactly as the
OV verifier and Chaldea's OV session credential do. Binding therefore rests on
the fixed credential file and username plus the signed single-node grant.
This is a documented property of the existing OV contract, not a widened
trust: no issuer, verifier or mapping changes.

Registration is a separate explicit opt-in, webmcp_interactive_ov_enabled,
off by default and accepted only with webmcp_interactive_enabled on the
laptop. The role refuses it on any other host, then checks the credential's
ancestors, private directory and file metadata without reading it. The
module's managed_helper set holds only the Jocasta tuple and this OV tuple:
name ov, its exact URL, Codex only, helper_host laptop only and empty extra.
Claude, OpenCode, other hosts, arbitrary helper strings, headers and OAuth
fields are refused. An explicit ov state=absent is honored.

The laptop activation is HELD. Its owning inventory,
inventory/host_vars/laptop/jocasta-interactive.yml, sets
webmcp_interactive_ov_enabled and a laptop-only webmcp_interactive_helper_sha256
for the reviewed aarch64 build ff9ccff552680ce1e86b3bed4c68c1a7902a0a0e7a0b5f9de174bc3d74b568fc
(Chaldea build 031e3362-b931-43e3-9da3-be31383e22dc). The shared architecture
pins and the other hosts are unchanged. Merging it activates ordinary laptop
pulls, so it stays unmerged until all of these hold: the separate ordinary OV
credential exists and is accepted; the reviewed helper is protected-staged;
root has accepted the full CHECK; and one bounded staging/merge/convergence
interval is ready. The installed helper's previous public SHA256,
f936deea9705fa4237f5c74760ccd51e1ab473fffa498836002f68b8c05036ba, is only an
explicit one-time operational upgrade guard (private
webmcp_interactive_previous_helper_sha256 for the staging run), not a permanent
acceptance list; inventory never carries it. The
[activation example](examples/laptop-ov-interactive-codex.yml) lists root's
preconditions and the self-sourced installed credential and helper. Upgrading the laptop's helper replaces the binary
that also serves its Jocasta registration, so root rechecks laptop Jocasta
after the upgrade. Native acceptance (allowed node read, sibling denial,
reuse past token lifetime) remains root's on-host evidence; the fixtures here
are not acceptance.

## Full interactive OV

The third closed helper tuple is, for HOST laptop or omarchy-pc only:

    /usr/local/libexec/webmcp-interactive-headers ov-full HOST

It gives ordinary interactive Claude and Codex on that host the whole OV
resources store through https://ov.mcp.ryzhkov.dev/mcp, with every document
action the server offers. It is a separate mode and identity rather than a
widening of the narrow `ov laptop` mode, which keeps its exact contract while
the server and enrollment transition is pending. One identity per host serves
both clients, as the managed Jocasta identity does; both have the same
authority, so separate accounts would add enrollment without reducing it.

homelab-infra's prepared full declaration
(playbooks/vars/authentik-ov-http-full-interactive.yml, selected only with
`-e ov_http_identities_full_interactive=true`) enrolls
chaldea-laptop-ov-full-interactive and chaldea-omarchy-pc-ov-full-interactive
under the same owned OV provider, issuer, client and signing key. Their signed
grant is `ov_namespaces: [viking://resources]` with
`ov_actions: [read, write, remove, maintain]`. The existing controller,
limited and narrow interactive identities keep their grants and claims. Fleet
never receives, reads, copies or checksums the delivered
~/.config/chaldea/authentik/ov-full-interactive.app-password.

Before any file access, the helper requires the host's actual machine and
account: the kernel node name and real UID must be omarchy-macbook-air-igor
and 1001 for laptop, or omarchy-pc and 1000 for omarchy-pc, as homelab-infra
binds the delivery. It finds the file from the account database's home for its
UID, ignoring HOME, and applies the same no-follow custody checks as the narrow
mode. It requests scope `ov.read ov.write ov.remove ov.maintain` with the
host's own username and the same fixed issuer, client, token and JWKS
endpoints. The response must carry exactly those four scopes, each once in any
order, and the token must pass the narrow mode's RS256, header, claim-count,
issuer, audience, client, lifetime and subject checks. It must then carry
exactly the resources-root namespace and exactly the four actions in canonical
order. An old read-only grant shape, a partial or reordered action list, an
unknown or duplicate action, a narrower or wider namespace and every foreign
or case-folded claim are refused. The narrow mode refuses any token carrying
an action claim, so neither mode accepts the other's token.

The module's closed `helper_profile: ov-full` keeps the registration name `ov`
and its exact URL, admits Claude and Codex only and approves only those two
hosts. Selecting it replaces the host's `ov` entry by name instead of adding a
second server with the same tools: on the laptop the narrow Codex entry is
replaced in place, and returning to the narrow selection is the same in-place
replacement. Any other profile, name, host, URL, provider, extra option or
stdio transport is refused, and OAuth mode still refuses helpers and headers.

Registration is a separate explicit opt-in, webmcp_interactive_ov_full_enabled,
off by default and accepted only with webmcp_interactive_enabled on laptop or
omarchy-pc, never together with webmcp_interactive_ov_enabled. The role then
checks the full credential's ancestors, private directory and file metadata
without reading it. No inventory selects it yet, and there is no helper pin
for this mode: the artifact is built only once the source is accepted. The
[inert activation example](examples/ov-full-interactive.yml) lists each
host's exact entries, binding, credential and preconditions.

Activation order per selected host: the server verifier that checks both
scope family and signed action is deployed; the full declaration is enrolled
with an identical repeat; the reviewed helper with this mode is staged and
pinned for that host; then that host's inventory sets the opt-in (on the
laptop removing webmcp_interactive_ov_enabled in the same change) and converges
with CHECK, REAL and an identical repeat. The installed narrow helper refuses
the full grant, so a consumer installed before the grant cannot silently
accept a wider token. The stdio ov-memory registration is unchanged by this
capability. After native parity is accepted for a host and provider, a
separate reviewed change retires exactly that ov-memory registration and
updates the fleet guidance to prefer the web tools. The stdio server tags
notes with OV_AGENT PROVIDER-HOST; one shared host identity cannot tell the
server which client wrote a note, so attribution is the server's own concern.

Clearing the opt-in alone removes nothing. Rollback for one host first
converges with the opt-in still set and an explicit `{name: ov, state: absent}`
remote entry, which removes the `ov` entry from both clients. Only then does
it clear the opt-in, restore the previous helper pin and, on the laptop,
re-select the narrow Codex mode if wanted. To stop issuance,
homelab-infra's full mode declares that host's full account absent; tokens
already issued remain valid until they expire.
