# Managed interactive Jocasta capability

Laptop acceptance and persistence are the base for this candidate. Its inventory,
ARM helper pin and protected tooling profiles remain unchanged. This source adds
explicit managed selections for agent-a, agent-b and omarchy-pc/GamingPC.
OpenCode is excluded. These three hosts still need protected staging and actual
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
remove the native consumer before deleting its staged credential/helper files.

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

Codex receives http_headers_helper; Claude receives headersHelper. The registration
module's auth_mode=managed_helper accepts only this fixed name, URL, command and
approved host. extra must be empty. Public auth_mode=oauth retains its existing
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

A future Web MCP service reuses the same host identity and protected credential.
It needs a separately reviewed explicit application policy/resource/scope grant
and registration/helper capability. Adding a URL creates no grant. This helper
currently supports Jocasta only. These controls do not isolate secrets from
arbitrary code running as the owning Unix user.
