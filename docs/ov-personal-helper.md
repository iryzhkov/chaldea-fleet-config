# Shared personal OV helper, source only

The existing `webmcp-interactive-headers ov-full HOST` command for laptop and
omarchy-pc retains its credential path, node/UID binding, issuer, client and
resource. Claude and Codex use the same helper on each host.

The fixed request now asks for the existing four resource scopes plus
`ov.personal.memory.read ov.personal.memory.write ov.personal.session.read
ov.personal.session.create ov.personal.session.append`. Returned tokens may
retain the old four-scope full resources contract with no personal claim, or
add a nonempty personal grant for exactly account default and user default.
Actions must be unique and follow memory.read, memory.write, session.read,
session.create, session.append order. Every claimed action requires its matching
personal scope. Known extra scopes are inert: only the signed action subset
confers authority. This permits reduced operator grants with the fixed expanded
scope request, matching HTTP af26. Personal scopes without any signed personal
claim still refuse, as do unknown or duplicate scopes, extra grant fields,
foreign owners, nulls, duplicate keys and case-folded claim aliases.

This is one broadened request, with no retry or issuer negotiation. An old
issuer that filters unsupported scopes and returns a valid old full token
continues to work. An old issuer that rejects unsupported requested scopes
will fail closed, even though its old tokens still validate. Live old-issuer
request handling was not tested under this source-only assignment. Root must
qualify the issuer transition before installing this artifact; token
compatibility alone does not establish exchange compatibility.

The narrow OV mode rejects personal claims. Jocasta, HoloNet, OpenCode, stdio
retirement and inventory pins are unchanged. No caller owner headers, identity
mapping, endpoint, cache, refresher, secret or dependency is added.

Contracts read at HTTP af26cfcd7a45c188ac6a468092ffa005f7fc0c42,
docs/personal-source.md, ov_http/auth.py, ov_http/config.py and personal_grant;
and infra 8c9cc5932eaf9f2b512b7fcf84a260a673fab999,
docs/ov-personal-contract.md. The HTTP runtime must separately bind actual
approved subjects and the backend owner. This helper validates subject shape
as before, not a newly invented subject-to-owner map. Session append remains
a separate backend qualification blocker in that HTTP source.

Root owns review, public CI, publication, accepted artifact pins, protected
issuer enrollment, HTTP/backend qualification, host installation and all four
native caller proofs. No deployment or credential access was performed here.
