# Restricted job hosts, protocol 1

This is fleet compute v0 for
[the Chaldea client](https://github.com/iryzhkov/chaldea), not an operator SSH
account. Both roles default off. Nothing is provisioned merely by merging.

## Host layout and enforced policy

- agent-a: `/srv/agent/chaldea-job`, always accepts.
- agent-b: `/srv/agent/chaldea-job`, always accepts.
- laptop: `/home/chaldea-job/jobs`, always accepts while it answers.
- omarchy-pc: `/home/chaldea-job/jobs`, idle gate enforced on the host.
  Every graphical session for `chaldea_job_host_desktop_user` must have
  loginctl LockedHint=yes. Every process owned by that user must have its exact
  comm name in `chaldea_job_host_idle_allowed_processes`. Sunshine, Steam,
  Wine/Proton, Lutris, Heroic and gamescope are refused even if listed.
  The baseline defaults empty, hence refuses until reviewed. Unknown processes
  fail closed. This deliberately also refuses harmless applications and an idle
  Sunshine daemon; it does not claim to distinguish active Sunshine streams.
  Do not allowlist games or general launchers. Running jobs are not preempted
  when the user unlocks in v0.

The user `chaldea-job` has no usable password and no sudo grants. The ordinary
operator sshd denies it through a Match drop-in; a separate sshd on TCP 2222
allows only that user. That daemon reuses the existing host Ed25519 key, uses
source-bound `restrict,from=...,command=...` authorized_keys, and also sets a
root-owned ForceCommand. It disables password/keyboard auth, PTY, user rc/env,
TCP/Unix/agent/X11 forwarding and tunnels. The complete operator config is
tested, its effective DenyUsers verified, then reloaded. The job daemon validates
its complete config before starting/restarting.

Managed blocks in UFW's IPv4 and IPv6 **before-input** chains accept the job
port only from the enrolled source IPs and drop other sources before ordinary
allow rules. Updating the block removes old source allowances. The role requires
UFW active, validates each rules file with iptables-restore --test, reloads UFW
before job admission, and leaves ordinary SSH rules intact. Use fixed addresses
(or DHCP reservations). Changing the port after initial enrollment also requires
removing any old compute-port rules/config and updating known-host entries;
do not leave an old manually managed daemon listening.

The self-contained Python server lives in this role's files, installed as
`/usr/local/libexec/chaldea-job-server-v1`; no repository deploy key is needed on
a job host for the client. Python, /usr/bin/bwrap and system build tools are used.
Only the client needs Node 26.10.0. No host mise config or operator runtime home is
mounted into a job.

Sandbox network is **on**, including loopback. No egress filtering is implemented.
Filesystem and environment isolation are enforced, not network service scopes.
The job has no host credentials or mounted control sockets. Native x86_64 and
aarch64 jobs only: seccomp blocks foreign ABIs and Btrfs subvolume/snapshot and
subvolume-flag ioctls, preventing nested-subvolume quota bypasses while leaving
GPU ioctls available.

A host lock admits one job at a time without a queue or polling. Busy hosts
refuse immediately. stdin EOF or SSH termination kills the process group;
bubblewrap parent-death/PID-namespace isolation also kills detached descendants.
SSH keepalives bound detection of silent partitions to about 30 seconds.
Workspaces are deleted after success and failure, including chmod-000 directories.
Stale state after SIGKILL/reboot is cleaned at next connection under the host
lock; a hard filesystem quota bounds it even if the host receives no further job.
No timer is installed. No result-reconnect or automatic retry exists.

The state directory has a 20 GiB hard limit, via a dedicated Btrfs subvolume's
referenced-byte qgroup or a Unix user quota on another filesystem. The role never
enables quotas or changes mount options implicitly. It refuses unsupported or
unprepared filesystems. New jobs also require 256 MiB free space plus 64 MiB input
capacity. Snapshot and aggregate artifact limits are 64 MiB each, output 64 MiB,
runtime six hours and upload two minutes. Both successful and failed workspaces
are deleted immediately; the three-day failed-workspace option is not used.
Authentication logs use a separate systemd journal namespace capped at 16 MiB
and 14 days. No command/output log is retained on the host. The client prunes
artifacts at 14 days and bounds its durable local journal to 1,000 entries /
14 days, protecting live client intents and refusing admission if no slot exists.

## Exact enrollment and apply procedure (orchestrator only)

Do these only after Igor approves the reviewed commits. Apply one host at a time.
No commands in this procedure were run against real hosts during implementation.

1. On **each source/session host** (agent-a, agent-b, laptop, omarchy-pc), as igor,
   generate its dedicated client key if absent. Never overwrite an existing key:

   ```sh
   test ! -e ~/.ssh/chaldea-job_ed25519
   umask 077
   ssh-keygen -t ed25519 -f ~/.ssh/chaldea-job_ed25519 -N '' -C "chaldea-job-$(hostname)"
   chmod 600 ~/.ssh/chaldea-job_ed25519
   ```

   Copy only the .pub contents to inventory. Never put a private key in inventory,
   command output, logs or a review. The role checks only existence, regular-file
   status, mode 0600 and ownership; it does not read key contents or generate keys.

2. Replace all TEST-NET addresses and PLACEHOLDER public keys in
   `inventory/group_vars/all.yml`:
   `chaldea_job_host_sources: [{name, ip, public_key}, ...]` lists every source;
   `chaldea_job_client_targets: [{name, address, port: 2222}, ...]` lists the four
   destinations. Public keys are ordinary inventory data. Use the actual source
   address the destination sees, not a hostname or a wildcard subnet.
   Add these values under each enrolled host in `inventory/hosts.yml`:

   ```yaml
   chaldea_job_host_enabled: true
   chaldea_job_client_enabled: true
   ```

   Keep normandy/homelab off. agent-a/agent-b already have data_disk_root=/srv/agent
   and must have that mount present. Their job policy defaults always. laptop
   defaults always and needs no awake detector. omarchy-pc already has policy
   idle: retain that and set `chaldea_job_host_desktop_user: igor` plus a reviewed
   `chaldea_job_host_idle_allowed_processes` baseline collected with
   `ps -u igor -o comm=` while locked and with games/Sunshine stopped. An empty
   baseline refuses all desktop jobs. Do not turn its policy to always.

3. Prepare and verify quotas **on each job host**. Determine the job filesystem:

   ```sh
   # agent-a and agent-b:
   findmnt -n -o FSTYPE,TARGET,OPTIONS --target /srv/agent
   # laptop and omarchy-pc:
   findmnt -n -o FSTYPE,TARGET,OPTIONS --target /home
   ```

   For Btrfs, an operator must enable consistent qgroups on that mount if not
   already enabled: `sudo btrfs quota enable MOUNT`, then
   `sudo btrfs quota rescan -w MOUNT`. This is a filesystem-wide accounting change
   and can take time; review it before running it. The role creates a fresh
   subvolume at the exact job path and sets its 21474836480-byte limit. An existing
   ordinary directory at that path is refused; move/remove it only after inspecting
   it and stopping any old job daemon. Never convert nonempty job state silently.

   For a non-Btrfs filesystem, enable filesystem-specific **user quotas** first.
   Do not run filesystem conversion/remount/quotacheck commands guessed from this
   document. `sudo quotaon -p -u MOUNT` must report on. The role assigns
   `setquota -u chaldea-job 0 20971520 0 0 MOUNT` after creating the user.
   Unsupported quota filesystems remain unenrolled rather than using a soft cap.
   Ensure UFW is already active and the ordinary SSH host Ed25519 key exists.

4. On omarchy-pc only, enroll the NVIDIA GPU if desired. Set
   `chaldea_job_host_gpu_devices` to the RTX 4090's actual NVIDIA device nodes
   (typically /dev/nvidia0, /dev/nvidiactl, /dev/nvidia-uvm and, if needed,
   /dev/nvidia-uvm-tools plus the NVIDIA render node resolved from its PCI
   by-path link). Determine PCI ownership with `lspci -nnk` and
   `ls -l /dev/dri/by-path/`; **do not assume renderD128 is NVIDIA**.
   Set `chaldea_job_host_nvidia_icd` to the installed NVIDIA Vulkan ICD JSON
   (often /usr/share/vulkan/icd.d/nvidia_icd.json) and
   `chaldea_job_host_gpu_groups: [video, render]` if device modes require those
   groups. Verify the nodes actually belong to the RTX 4090, not the AMD iGPU
   (which is normally Vulkan device 0). Leave these empty on CPU-only hosts.
   Without --gpu no GPU nodes are mounted. With missing GPU enrollment the host
   refuses the request. No real GPU job was run in this implementation.

5. Commit/review the concrete inventory, then run on each host itself, as igor,
   from its reviewed fleet-config checkout. Set HOST to exactly agent-a, agent-b,
   laptop or omarchy-pc for that machine:

   ```sh
   export TMPDIR="$HOME/.cache/chaldea-apply"
   mkdir -p "$TMPDIR"
   ANSIBLE=~/.local/share/chaldea/ansible-core-2.19.14/bin/ansible-playbook
   "$ANSIBLE" -i inventory site.yml --limit HOST --tags chaldea_job_host,chaldea_job_client --check --diff
   "$ANSIBLE" -i inventory site.yml --limit HOST --tags chaldea_job_host,chaldea_job_client
   "$ANSIBLE" -i inventory site.yml --limit HOST --tags chaldea_job_host,chaldea_job_client
   ```

   Add --ask-become-pass if that host needs it. Read the check diff first.
   Quota setters are idempotent absolute assignments and report unchanged.
   The second real run should have changed=0. Verify:

   ```sh
   sudo sshd -t
   sudo sshd -t -f /etc/ssh/chaldea-job-sshd.conf
   sudo systemctl is-active chaldea-job-sshd.service
   sudo ufw show before-rules
   # Btrfs, using the host's job path:
   sudo btrfs qgroup show -r --raw JOB_PATH
   # Or, for other filesystems:
   sudo quota -w -u chaldea-job
   ```

6. On **each source host**, pin every destination's existing host Ed25519 **public**
   key through a trusted operator path (console/existing verified operator SSH),
   verifying its fingerprint. Add a line per destination to
   `~/.ssh/chaldea-job_known_hosts` as
   `[DESTINATION-IP]:2222 ssh-ed25519 PUBLIC-KEY`, mode 0600. The role deliberately
   does not trust an unauthenticated ssh-keyscan response. Install the reviewed
   Chaldea client with Node 26.10.0; run `npm ci`. From a disposable Git worktree,
   run `node /PATH/TO/chaldea/bin/chaldea exec --host agent-a -- printf ready`,
   then an artifact test and a repeated invocation. Repeat admission tests for
   agent-b, laptop (awake), and omarchy-pc locked/busy, plus a GPU smoke test if
   enrolled. Confirm ordinary `ssh chaldea-job@HOST` and forwarding are denied.

For immediate revocation stop `chaldea-job-sshd.service` and update/remove its
authorized keys. Setting the enrollment switch false only skips future applies;
it does not revoke an already deployed daemon.

## Local checks and remaining deployment evidence

`CI_PYTHON=$(uv python find 3.13) bash tools/ci.sh` covers the repository gates,
server validation/idle-policy/sandbox/cleanup tests, rendered client config and
unsafe key metadata refusal, plus the existing synthetic double convergence.
Set TMPDIR to disk-backed scratch before invoking it.

The companion client's `npm run exec:e2e`, with CHALDEA_JOB_SERVER pointing at
this role's file, uses real unprivileged sshd and bubblewrap on loopback only.
It proves streaming/status, artifact delivery, cleanup, shell/PTY/forwarding
refusal, no host sockets/credentials/sudo/GPU, quota-escape syscall refusal,
disconnect descendant termination, and injected admission limits.
It cannot prove real firewall rules, installed filesystem hard quotas, a real
RTX 4090 execution, actual desktop baseline suitability or real-host convergence.
Those are the orchestrator's post-approval acceptance checks. No real host was
updated or verified by this implementation lane.
