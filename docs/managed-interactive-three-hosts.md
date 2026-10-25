# Three-host managed Jocasta staging

This candidate selects agent-a, agent-b and omarchy-pc for ordinary interactive
Codex and Claude. Laptop is already accepted and stays unchanged. OpenCode is
excluded. Merging these flags enables ordinary pull convergence, so this branch
must stay unpublished until root qualifies the exact source, protected staging,
review and CI. Source tests do not establish live readiness or native acceptance.

## Per-host inputs

| Inventory host | Actual hostname | Unix user / UID | Actual home | Architecture |
| --- | --- | --- | --- | --- |
| agent-a | agent-a | igor / 1000 | /home/igor | x86_64 |
| agent-b | agent-b | igor / 1000 | /home/igor | x86_64 |
| omarchy-pc | omarchy-pc | igor / 1000 | /home/igor | x86_64 |

These identities were observed read-only for this slice; root must recheck them
at staging. Canonical local Ansible derives fleet_home from user_dir, never from
an assumed UID or the inventory alias. Laptop keeps its accepted host selection
and shared aarch64 pin. No laptop observation is an acceptance prerequisite for
this source-only change.

Use the retained AMD64 artifact from build
23d824a7-069a-4b74-a085-88ff6442fb60, SHA256
667cd06e83a091d607306e6486ff079d0065038abf2db64b87234d15492bd6ed.
Do not rebuild it. Missing helper/enrollment delivery or an unsupported
architecture must fail before native registration.

## Root's protected staging and source delivery

1. Reconcile active pull/Ansible writers and timer deadlines before every
   bounded host interval. Agent-a has an unresolved ordinary CLI installation
   failure. This candidate neither repairs nor exempts that failure.
2. Root enrolls each dedicated host identity through the existing mechanism.
   Deliver only that host's protected enrollment to its actual local controller.
   Keep credentials and receipt/generation digests out of source, argv, logs and
   diffs. Preserve backend policy and the accepted laptop.
3. Stage the retained public helper and protected enrollment on that host before
   allowing any ordinary pull of this candidate. Use a private 0600 extra-vars
   file with initial staging paths. The enrollment parent must be UID-owned
   0700; its regular file must be UID-owned 0600 with one link and no symlinks.
   The helper destination is root-owned 0755 at
   /usr/local/libexec/webmcp-interactive-headers.
4. Deliver the exact reviewed source through root's guarded staging procedure,
   without exposing opt-in flags to ordinary pulls prematurely. Run the pinned
   host-local ansible-core 2.19.14 with canonical site.yml, the actual inventory
   alias and --tags mcp_registrations. Review CHECK/diff before REAL. That tag
   also converges existing unrelated registrations, so root must bound its diff.
   The actual-host identity assertion remains mandatory.
5. After initial delivery, repeat canonical local convergence with inventory's
   installed source=destination paths, without staging-path overrides. Require
   REAL and second REAL success and second REAL changed=0 failed=0 unreachable=0.
   Preserve unrelated MCP entries and protected tooling profiles. Missing inputs
   must fail closed, never silently select public OAuth.
6. Hand acceptance to a native T3 session started explicitly on each host.
   Remote T3 launch is unsupported. Do not fork another host's session or copy
   native authentication caches. Root must obtain actual Codex and Claude full
   Jocasta proof, write/CAS behavior, and helper reuse after >330s. Keep proof
   separate from synthetic test evidence.
7. Root owns final review/CI, publication, activation and per-host acceptance.
   Recheck versions and timer state at that boundary. A source commit alone
   does not make this candidate safe to activate.

## Rollback prerequisites

Retain each host's prior named Jocasta state and native entry metadata before
staging. The three hosts' prior interactive entry absence needs explicit
state=absent for the owned Jocasta registrations before removing the opt-in;
enabled=false alone does not remove an entry or protected files. Restore only
the affected host selection and owned entry. Keep unrelated entries, backend
configuration and laptop unchanged.

Root must retain the receipt-bound revocation procedure and protected initial
delivery inputs. Existing-file rotation requires the exact private previous
credential digest; helper replacement requires the reviewed previous public
digest. Remove owned enrollment/helper files only after proving no consumers
remain. A backend rollback or native logout needs root's concrete separate
decision; never use global logout or copy unrelated authentication.
