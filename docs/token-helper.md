# Service token helper enrollment

This activation follow-up enrolls the access-trust updater on agent-a only.
The helper remains disabled everywhere. Hold this PR until host-v0.2.1 is pinned
and the orchestrator provisions transport, private state and root-pinned Node,
then verifies check mode, a real apply and a second apply with changed=0 on
agent-a. The live pull timer follows main, so merging enrollment is activation.
The orchestrator owns that merge; do not arm auto-merge for this follow-up.

After Akasha step 9, the orchestrator can set chaldea_token_helper_enabled on one
host, with a reviewed client release version and SHA-256, producer grants and
matching signed issuer ceilings/source registrations. TODO: pin the first client
release containing configurable issuer identity, at least client-v0.2.1.
Do not point the role at client-v0.2.0.

The role independently downloads and verifies a client release as root through
the shared chaldea_client_release verifier. It installs under
/opt/chaldea-token-helper/releases. It never runs the user client. Node comes
from the inventory's reviewed archive checksum, installed as root beside the
client. bin/chaldea-token-helper is copied from that release. The issuer wrapper
clears environment, preserves only sudo's SUDO_UID and a fixed PATH, and invokes
the root-pinned Node and client entrypoint.

Issuer config fields are uid, key_file, name and kid. Defaults retain agent-a's
UID 995, /var/lib/chaldea-issuer/keys/agent-a-2026-10.pem, chaldea:agent-a and
agent-a-2026-10. The role requires an existing non-login chaldea-issuer account
matching that UID, an issuer-owned 0600 signing key and initialized private state.
It does not create keys, initialize state or change source registrations.

Each grant has uid, audience, action, source, host, kind, profile and project.
It permits one exact sudo argument string as chaldea-issuer. The application also
checks all five selectors and grants, current signed trust and clock health.
The role validates sudoers with /usr/sbin/visudo -cf before replacing the drop-in.
No wildcards, SETENV, shell, Node or arbitrary Chaldea command is granted.

After setting the pins and explicit enrollment, run on agent-a only:

```sh
ansible-playbook -i inventory/hosts.yml site.yml --limit agent-a --tags chaldea_access_trust,chaldea_token_helper --check --diff
ansible-playbook -i inventory/hosts.yml site.yml --limit agent-a --tags chaldea_access_trust,chaldea_token_helper
```

Read the helper configuration, ownership and sudoers validation, then verify trust
and clock timer health before enabling a producer. Activation and canary
publication belong to the orchestrator after Akasha step 9.
