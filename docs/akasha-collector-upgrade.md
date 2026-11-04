# Upgrade existing Akasha collectors

The published host-v0.2.16 package repairs retained cursor pagination and slow
tool-call delivery. Its archive SHA-256 is
d9cdc7e86a37b8559a534e99bfa3216a127db5c701c8e86f51291bc52f8cc186.
Workflow41790129018 qualified the exact reviewed source179f465. The collector
lives under /opt/chaldea-akasha-host/releases and /var/cache/chaldea-akasha-host.
The existing canonical artifact role installs it with role-local parameters;
shared trust/job022 and clock012 keep their own roots and pins.

Run the narrow play on each existing producer account with pinned Ansible2.19.14:
`ansible-playbook -i inventory/hosts.yml playbooks/akasha-collector-upgrade.yml --limit HOST --check --diff`.
HOST is the normal inventory alias: agent-a, agent-b, omarchy-pc, laptop, homelab
or normandy. It binds the real hostname, UID, account and home against the existing
enrollment policy, and requires an already enabled timer. It does not enroll a host
or change helpers, trust, permissions, capture, spools, locks or database paths.

Review CHECK, apply without --check, then apply again and require changed=0.
Preserve prior unit files and snapshot every old shared release/cache member,
hash and persistent metadata before REAL. Require all of those unchanged after.
The collector timer remains enabled; an existing oneshot may finish with its old
executable, so confirm a subsequent invocation uses016. Compare delivery counters
and actual occurrence timestamps through authenticated Akasha reads.

Normal fleet convergence keeps the same independent collector selection. Homelab
and Normandy retain the already enabled collectors as explicit inventory settings.
Server timer outcomes retain their existing feed route because those accounts have
no fleet job_finished grant. No grant is added. Homelab's shared022 preservation
list retains all ten old releases if that separate
installer is later invoked. The upgrade play itself invokes only the collector
and its independently scoped artifact installation.
