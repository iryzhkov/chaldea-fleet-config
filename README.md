# chaldea-fleet-config

Fleet configuration for the Chaldea hosts: inventory, roles and pinned releases. Hosts converge from this repository (decision D21, roadmap r18 item 1.15).

Secrets appear only as SOPS+age references. Unit p1-1-15a-fleet-config-repo supplies CI, inventory, guarded roles and binary pins.

Bootstrap is offline preparation only. Every inventory adoption flag and the pull
timer are disabled. The controller validates locally and refuses unfinished
worker, coordinator, timer or live-preflight intent in normal and check mode,
before gathering remote facts or opening SSH. Disabled validation reports
"not converged"; it proves no runtime adoption.

Clone this repository using the existing repository identity, then from its root:

```sh
env -u VIRTUAL_ENV -u PYTHONPATH bash tools/bootstrap-ci.sh
env -u VIRTUAL_ENV -u PYTHONPATH bash tools/with-ci-env.sh python3 -m unittest discover -s tests -v
env -u VIRTUAL_ENV -u PYTHONPATH bash tools/with-ci-env.sh ansible-lint
```

The exact gates are `bash tools/with-ci-env.sh python3 -m unittest discover -s tests -v`
and `bash tools/with-ci-env.sh ansible-lint`. Workflow and job are both
`ci`, on every PR and main push, with read-only contents permission.
Bootstrap requires tested Python 3.13.5 and resolves no new versions: the complete
wheel hash lock installs ansible-core 2.19.14, ansible-lint 26.10.0 and PyYAML 6.0.3
into ignored .venv-ci. The lock targets Linux x86_64 CI/workers, not fleet runtime
interpreters. Bootstrap may fetch those pinned wheels; both core gates are offline.
The wrapper clears inherited Python activation/path state and verifies all locked
versions and required executables on each call. Caches and temporary files stay
under .cache-ci. Installation or verification failure stops the command.

Safe local check/diff uses synthetic temporary inventory only:

```sh
mkdir -p .cache-ci
cat > .cache-ci/synthetic.yml <<'YAML'
all:
  children:
    pull_runner:
      hosts:
        synthetic_runner: {ansible_connection: local}
    fleet_targets:
      hosts:
        synthetic_runner:
          ansible_connection: local
          adopted: false
          desired_role: worker
          desired_order: 1
YAML
bash tools/with-ci-env.sh ansible-playbook -i .cache-ci/synthetic.yml fleet.yml --check --diff
```

Do not execute the production inventory during bootstrap. Later, the sole
pull_runner must use ansible-pull's `--limit all`: its default local-host
limit excludes remote fleet plays. One runner plus inventory ordering and serial
worker/coordinator plays provides fleet ordering; independent local timers do not.
No timer or active service is created here.

All host facts and identity literals belong to inventory/hosts.yml. Historical
observations retain source digest/provenance and probe limitations; runner SSH
resolution is distinct from probe aliases and persistent-SSH catalog addresses.
Observed backlog acceptance stays true even for the desired coordinator-only
target; resolving that policy is live-adoption work. Logical state candidates and
open database descriptors are separate evidence, including empty descriptor lists.

pins.yml describes the binary release and source only. Configuration revision is
the fetched fleet-config Git HEAD, never the binary source SHA. Until Renovate
2.12c the orchestrator opens pin PRs and Igor merges them. Later exact-CI must bind
both revisions independently. Source CI availability does not prove exact main
push verification or deployed runtime.

Unit b supplies pinned exact-CI, worker activation and runner timer/locking;
unit c activates the coordinator after Litestream; unit d handles onboarding.
Before live use, confirm service-user/systemd access, protected file permissions,
OS/interpreter compatibility, observation freshness, runner fetch/decrypt access,
read-only Actions/release API access, age recovery and credential reference mapping.
The required ci merge check is an operator step after landing. Existing deployment
and backup operations remain until attended cut-over and D21 prerequisites.
