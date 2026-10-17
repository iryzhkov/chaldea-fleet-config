# Restricted job hosts, protocol 1 — fix round 2

Both roles default off. No real host has been provisioned by this lane. The
client is in iryzhkov/chaldea PR #2; these roles are PR #3. Apply only after the
reviewed pair and the concrete public-key inventory are approved.

## Enforced behavior and limits

- agent-a and agent-b accept jobs while up, using /srv/agent/chaldea-job.
- laptop accepts while awake, using /home/chaldea-job/jobs.
- omarchy-pc uses /home/chaldea-job/jobs and policy idle. A Steam game or
  Minecraft refuses admission. Sunshine and the Steam client do not.
- Steam defaults to a reaper command line containing SteamLaunch AppId=<number>,
  plus its descendants. Minecraft defaults to java running net.minecraft,
  Fabric's knot launcher, or a .minecraft/.minecraft-modded game directory.
  Inventory can override chaldea_job_host_steam_game_pattern and
  chaldea_job_host_minecraft_pattern. No LockedHint or Sunshine test remains.
  A five-second check runs only during an idle-policy job. Gaming appearance
  sends SIGTERM to the job group, followed by SIGKILL after ten seconds if
  necessary. Client journal/status says preempted; it never retries.
- One job per host; six-hour runtime, two-minute upload, 64 MiB snapshot,
  64 MiB combined output, 32 regular-file artifacts / 64 MiB aggregate.
- Every job has its own network namespace, connected outward by pasta.
  Host-loopback/gateway mapping, automatic port forwarding and socket splicing
  are explicitly disabled. An nft output filter in that namespace rejects
  every non-loopback address assigned to the host and connected subnets of all
  interfaces outside the IPv4/IPv6 default routes (including Docker bridges and
  Nebula overlays). DNS resolvers in these blocked ranges are replaced by public
  fallback resolvers. Pasta's unused DHCP/NDP DNS discovery is explicitly disabled
  with --dns none, avoiding its cosmetic warning on loopback-stub hosts; the guest
  still uses its sanitized resolv.conf for DNS.
  These addresses/subnets are captured at job start; dynamic
  interface changes during a job remain follow-up N2. Guest loopback stays inside
  the guest and host abstract Unix sockets are absent. Outbound DNS/HTTPS works.
  This is host isolation, **not a general internet/LAN egress allowlist**.
- bubblewrap shares only pasta's new namespace, never the host namespace. It
  creates the remaining namespaces and supplies a fresh HOME/TMPDIR, read-only
  system tools and public resolver/certificate files, and the writable workspace.
  No host credentials, sudo, Huyang/Docker/SSH-agent/D-Bus sockets are mounted.
  Nested user namespaces are disabled when bwrap supports --disable-userns.
  The root-owned forced command uses python3 -I.
- GPU devices are absent unless --gpu. Enroll verified RTX 4090 device nodes and
  its NVIDIA ICD, never the AMD iGPU (normally Vulkan device 0).
- The job sshd cgroup applies MemoryMax, MemorySwapMax=0 and TasksMax.
  Defaults: agent-a 8G/512 tasks, agent-b 4G/512, desktop 4G/256, laptop 2G/128.
  The generic default is the smaller of 4 GiB and half the detected RAM; apply
  refuses any inventory MemoryMax above half RAM. Recheck this after VM resizing.
  Its dedicated top-level chaldea.slice is a direct sibling of user.slice, with
  CPUWeight=10 (versus user.slice's default 100), IOWeight=10 and a CPUQuota of
  50% of the host's logical cores (8 cores => 400%, since 100% is one CPU).
  Variables chaldea_job_host_memory_max, _tasks_max, _cpu_weight, _io_weight and
  _cpu_quota are operator-adjustable. /dev/shm is a private size-limited tmpfs, default
  64 MiB (chaldea_job_host_shm_bytes), and counts against MemoryMax.
- Storage is one fixed-size sparse ext4 image, default 21474836480 bytes
  (chaldea_job_host_image_bytes). No filesystem-wide quotas are enabled.
  Default image: /srv/agent/chaldea-job.ext4 on agents, otherwise
  /home/chaldea-job-state.ext4; chaldea_job_host_image overrides it.
  Before creating a new sparse image, the role checks backing-filesystem free
  space for its full configured size and refuses if insufficient. This is an
  apply-time check, not a reservation against later unrelated disk writers.
  On btrfs, creation applies chattr +C (No_COW) to the empty new file before
  truncating/formatting it. Existing images are never reformatted, resized or
  given new attributes. On omarchy-pc, /home is the @home subvolume outside
  snapper's root configuration; the default image lives there. Put images outside snapshot
  coverage (or explicitly exclude them) if the containing filesystem has snapshots.
  Admission checks free space on the image filesystem, reserving 256 MiB + input.
- Normal/failed workspaces are deleted immediately. fd-relative cleanup handles
  paths beyond PATH_MAX and chmod-000 directories. Startup/end cleanup has a
  one-second budget, logs bounded leftover warnings and continues after failures.
  Unremovable/crash leftovers stay inside the image bound; new work proceeds if
  space remains. No cleanup polling timer exists. Authentication logs have a
  separate 16 MiB / 14-day journal namespace.
- Client artifacts are capped at 20 GiB per destination across all worktrees,
  using paths in the journal; age is 14 days, with older completed artifacts
  evicted under size pressure. Journal eviction also removes its artifacts.
  A per-host kernel flock protects accounting and vanishes on crash/reboot.
  Definite non-execution is refused; dispatched/lost outcomes remain uncertain.
  Remote exit 125 passes through; local Chaldea failures use 255, as with SSH.
  A remote 255 is distinguished by the finished journal entry.

## Boot and reboot contract

The image has an enabled path-named systemd .mount unit. It has nofail,
DefaultDependencies=no, no Before=multi-user.target and no hard dependency from
that target. A missing image skips it; a corrupt image fails its mount within
five seconds. Neither can hold boot waiting for job storage.

chaldea-job-sshd.service is enabled independently, with **no mount dependency**.
It stays available and returns "job storage unavailable: image is not mounted"
until storage is ready. It never writes jobs to the underlying mountpoint.
When storage returns, the next explicit invocation works; startup removes killed
jobs' leftovers within its budget. The chosen compute firewall is enabled at
boot: UFW's persistent IPv4/IPv6 before-chain rules, or the dedicated nft unit
below. No role enables the distro nftables.service.

The operator sshd denies chaldea-job; the compute-only daemon on TCP 2222 allows
only that account. Root owns .ssh and authorized_keys. Every source key has
restrict,from=<exact IP>,command=<isolated Python forced command>. Password,
keyboard auth, PTY, user rc/env, tunnels and TCP/Unix/agent/X11 forwarding are
disabled. Main-sshd configuration is tested including its effective DenyUsers
rule case-insensitively. Failed validation removes the drop-in without reloading
an invalid configuration. The selected backend restricts the compute port to
enrolled source addresses. Changes to port/source inventory replace only the
managed UFW block or dedicated nft table.

Neither role connects to peers at boot. Session hosts only get static SSH config
and metadata checks. Job hosts only need local disk, firewall and sshd.
Source/target reboot during dispatch leaves durable intent uncertain. There is
no reconnect/replay path. A trusted supervisor outside pasta owns the parent-death
signal and kills the transport group if the forced server dies; this also covers
older Debian pasta versions that clear their own inherited parent-death signal.
A pipe-based lifetime guard also kills the group if the supervisor is SIGKILLed.
Smoke tests always kill their launch group before deleting temporary storage or
releasing admission. Stale ControlMaster sockets are checked and removed before
a new dispatch; flock needs no stale-lock cleanup.

## Compute-port firewall modes and removal

chaldea_job_host_firewall selects ufw (default) or nft. Inventory selects nft for
agent-a; this does not change policy for its operator SSH, T3 ports or Docker.

- ufw requires an already-active UFW before proceeding. It maintains source-bound
  TCP compute rules in the IPv4/IPv6 before chains and enables UFW persistence.
  An inactive UFW causes a clear failure; the role does not silently enable a
  new host-wide policy.
- nft does not install or invoke UFW. /etc/chaldea-job.nft contains only the inet
  chaldea_job table, accepting the configured TCP compute port (default 2222)
  from IPv4/IPv6 enrolled-source sets and dropping other TCP traffic to that port.
  The input chain accepts other traffic without overriding any other firewall's
  decision. It has no forwarding, output or Docker rules. One atomic nft -f
  transaction adds/deletes/recreates only chaldea_job, validated first with
  nft -c -f. Commands use /usr/sbin/nft on Debian and Arch (Arch's merged
  /usr/sbin points into /usr/bin). It never flushes the global ruleset or modifies
  another table.
- chaldea-job-firewall.service is an enabled oneshot with RemainAfterExit, no
  default boot ordering and a five-second timeout. It runs only the dedicated
  file, validates on start/reload, and has no dependency on peers or networking
  being online. Boot continues if it fails. Job SSH requires/starts after this
  unit and checks that the table is loaded before listening, including on reboot.
  Apply refuses if the distro nftables.service is enabled, without changing it:
  Debian's global /etc/nftables.conf loader can flush the compute table and
  Docker's rules. Never enable it alongside this role. The dedicated unit orders
  after nftables.service if both are started, without pulling that service in.
- Stopping the dedicated firewall unit leaves its table installed. To remove nft
  enrollment, set chaldea_job_host_enabled=false in inventory, then as operator:
  ```sh
  sudo systemctl disable --now chaldea-job-sshd.service
  sudo systemctl disable --now chaldea-job-firewall.service
  sudo /usr/sbin/nft delete table inet chaldea_job
  sudo rm /etc/chaldea-job.nft /etc/systemd/system/chaldea-job-firewall.service
  sudo systemctl daemon-reload
  ```
  If the table is already absent, omit its deletion. Keep other tables and the
  distro service configuration unchanged. For UFW removal, stop/disable job SSH
  first, remove only the CHALDEA JOB V0 managed blocks from before.rules and
  before6.rules, then ufw reload; do not disable the host's existing firewall.
  Switching backends does not automatically remove old backend rules; coordinate
  that removal with jobs stopped.

Packages use ansible-core only: Debian ensures python3-apt before collecting
package facts and uses apt; Arch reads package_facts through
pacman and runs pacman -S --needed --noconfirm only for missing packages, with
English transaction output determining changed status. No community.general
collection is required. Arch check mode reports missing packages and skips the
install command; missing sandbox-package version checks are explicitly deferred
until installation on apply. Installed-version checks run normally when both
baseline packages exist.

## Enrollment and apply (orchestrator, after approval)

1. On each source host (agent-a, agent-b, laptop, omarchy-pc), as igor, create
   ~/.ssh/chaldea-job_ed25519 **only if absent**:
   `umask 077; ssh-keygen -t ed25519 -f ~/.ssh/chaldea-job_ed25519 -N ''`.
   Keep its private half mode 0600. Copy only .pub and its fixed source IP into
   chaldea_job_host_sources in inventory/group_vars/all.yml. Replace every
   PLACEHOLDER/TEST-NET value. chaldea_job_client_targets lists actual destination
   addresses and port 2222. No new repository deploy key is needed for job hosts.
2. In inventory/hosts.yml enable chaldea_job_host_enabled and
   chaldea_job_client_enabled per enrolled host. Keep normandy/homelab off.
   Preserve omarchy-pc policy idle; agents/laptop default always. Resource defaults
   are already conservative. Review pattern and image-size overrides if needed.
   The /srv/agent filesystem must already be mounted on agent-a/b.
3. On omarchy-pc, optionally set chaldea_job_host_gpu_devices to the RTX 4090's
   actual /dev/nvidia* nodes plus its PCI-resolved render node, _nvidia_icd to its
   NVIDIA ICD JSON and _gpu_groups to [video, render] if permissions require it.
   Inspect lspci -nnk and /dev/dri/by-path; do not guess renderD128 or Vulkan index.
4. No quota conversion, remount, Btrfs qgroup enablement or snapper change is
   required. Ensure the chosen image path has space, is outside snapshot coverage,
   and is absent or already the reviewed fixed image. Do not overwrite an image
   or move old job data without inspection. A leftover .ext4.new from interrupted
   first creation is never overwritten; inspect/remove it before repeating apply.
5. From the reviewed fleet checkout on **each host itself**, with HOST set to that
   machine's inventory name, run:
   ```sh
   export TMPDIR="$HOME/.cache/chaldea-scratch/laneC"
   mkdir -p "$TMPDIR"
   ANSIBLE=~/.local/share/chaldea/ansible-core-2.19.14/bin/ansible-playbook
   "$ANSIBLE" -i inventory site.yml --limit HOST --tags chaldea_job_host,chaldea_job_client --check --diff
   "$ANSIBLE" -i inventory site.yml --limit HOST --tags chaldea_job_host,chaldea_job_client
   "$ANSIBLE" -i inventory site.yml --limit HOST --tags chaldea_job_host,chaldea_job_client
   ```
   Add --ask-become-pass if needed. Review the check diff before apply; the second
   real apply should report changed=0. The role requires passt >= 2025-05-03 and
   bubblewrap >= 0.9 (size-limited tmpfs), checks required networking options, and
   runs the exact pasta+bwrap launch as chaldea-job against mounted job storage.
   A failed smoke test fails apply clearly before enabling new SSH access. An
   absent mount skips this storage-dependent smoke and jobs refuse until mounted.
   Repeat apply once mounted; do not accept enrollment without a passing smoke.
   Older distro pasta uses a PID namespace: the server translates bwrap's status
   PID through /proc within the transport's descendant tree. It does not require
   --no-pidns. The optional -c socket flag is feature-detected. The role installs passt, nftables,
   bubblewrap, SSH and e2fsprogs, plus UFW only in ufw mode. It creates/formats
   only a new image, enables the optional mount, chosen firewall and job daemon.
   No step contacts another host.
6. On every source, pin each existing destination host Ed25519 public key through
   a trusted console/verified operator SSH path. Put
   `[DESTINATION-IP]:2222 ssh-ed25519 PUBLIC-KEY` in
   ~/.ssh/chaldea-job_known_hosts (0600), verifying the fingerprint.
   Install the reviewed client with Node 26.10.0 and npm ci. Client flock/ssh
   are system tools; no session-host service is added.

## Per-host acceptance, including reboot

Run these on agent-a, agent-b, laptop and omarchy-pc, one host at a time:

- Validate sudo sshd -t and sudo sshd -t -f /etc/ssh/chaldea-job-sshd.conf.
  Verify job daemon, chosen firewall unit and the path-named mount are enabled, then inspect
  systemctl show chaldea-job-sshd -p MemoryMax -p TasksMax -p Slice, then
  systemctl show chaldea.slice -p CPUWeight -p CPUQuotaPerSecUSec -p IOWeight.
  Confirm MemoryMax <= half physical RAM and CPUQuota equals the reviewed budget.
  Inspect findmnt JOB_ROOT. In ufw mode inspect sudo ufw show before-rules;
  in nft mode inspect sudo nft list table inet chaldea_job and validate
  sudo nft -c -f /etc/chaldea-job.nft. Confirm enrolled IPv4/IPv6 sources can
  reach TCP 2222 and other sources cannot. Confirm ports 22, 7391 and 45011
  and Docker connectivity retain their previous behavior. Confirm ordinary
  chaldea-job SSH and forwarding are refused.
- From a disposable Git worktree run output/status/artifact tests, including a
  command returning 125. Repeat to measure warm startup. Inside a job check
  /dev/shm size and absence of the host HOME, sockets and credentials.
- Start a temporary host TCP listener on loopback and on a host LAN address,
  plus an abstract Unix socket. Confirm a job cannot connect to either listener
  or see/connect to the abstract socket; confirm its own loopback works and
  outbound DNS plus HTTPS succeed. Also test a reachable container/overlay peer
  on each non-default connected subnet: its service must be unreachable from a
  job. Verify the detected Docker/Nebula prefixes and default-route interface
  before testing. Stop the temporary listeners.
- On omarchy-pc specifically: Sunshine and the Steam client alone must permit
  admission. Launch a Steam game, then Minecraft (including the modded/Fabric
  path); each must refuse a new job. During a long running job, start either
  game: observe preempted status within five seconds plus at most ten seconds of
  SIGTERM grace. Check the real process table matches the default patterns.
  Perform an RTX 4090 smoke test only if GPU enrollment was approved.
- Reboot each target during a harmless long job: the source journal must remain
  uncertain, with no rerun. After boot verify local boot succeeds independently
  of every peer's availability, units are enabled/active, selected firewall rules persist,
  old workspaces are cleaned and a new explicit invocation succeeds.
- Reboot each source during a harmless job. After boot confirm its journal is
  uncertain, no automatic job starts, and its next explicit command succeeds
  without manual ControlMaster/lock cleanup.
- On each host, in an approved maintenance window with jobs stopped, test missing
  image and a corrupt **disposable test image**. Never corrupt the real image:
  temporarily override the mount's What/ConditionPathExists to the test path.
  Reboot: boot must complete, job sshd must answer with the storage-unavailable
  refusal, and peers must boot normally while this host is down. Restore the
  reviewed mount configuration/image, start its mount, verify a new call works
  without restarting the job daemon, and repeat a clean apply.

Stopping chaldea-job-sshd.service revokes admission immediately. An enrollment
switch false merely skips future applies and does not revoke an installed daemon.

## Validation boundary

Local: CI_PYTHON=$(uv python find 3.13) bash tools/ci.sh; companion exec:check,
exec:test and exec:e2e with CHALDEA_JOB_SERVER explicitly pointing to this role.
E2E renders the shipped sshd/key templates. It tests real unprivileged SSH and
bubblewrap/pasta, DNS/HTTPS, host TCP/abstract isolation, TERM/KILL preemption,
disconnect after output closes, missing mount, stale sockets and startup cleanup.
DNS/HTTPS skips only when the host itself lacks that connectivity. System
/usr/bin/pasta is the E2E default. CHALDEA_PASTA is an explicit override only;
never validate a newer fixture in place of the enrolled hosts' distro packages.
Local omarchy-pc has no installed passt, and this lane cannot install packages on
real hosts. Round 2 therefore tests the exact extracted Arch mirror package
2026_07_28.f8df3f1-1 and Debian 13 candidate
0.0~git20250503.587980c-2+deb13u1 against system bubblewrap 0.12.0, using explicit
CHALDEA_PASTA overrides in disk-backed scratch. Agent-a/b were inspected read-only:
Debian 13, no passt/bubblewrap installed; candidate bubblewrap 0.12.0. Laptop's
Arch ARM mirror offers passt 2026_10_02 and bubblewrap 0.13. Enrollment must pass
the same smoke with its actual installed packages; no package was installed here.

Real image mounting/cgroup enforcement, host reboot/boot ordering, firewall
effects, default game-pattern suitability and RTX 4090 execution remain
post-approval deployment acceptance. No real host was updated in this lane.
