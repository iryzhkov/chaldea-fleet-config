# Independent clock runtime

Clock checks and trust-bundle installation use the checksum-pinned
`chaldea_clock_host_version` artifact under `/opt/chaldea-clock-host/releases`.
The existing host artifact installer manages its separate
`/var/cache/chaldea-clock-host` cache and retains the newest prior clock release.

The shared host, job, collector, issuer and publisher pins stay unchanged.
An ordinary shared-host installation never scans or prunes the clock root.
This avoids changing implicit rollback retention when a clock repair is installed.
The clock service's sandbox already allows its accepted-evidence sidecar under
`/run/chaldea-access-trust`; credentials and trust grants are unchanged.

Deploy with the trust role only, review check-mode output, apply twice and
require the second recap to have zero changes. Verify both clock health and
credential-backed delivery. New installations need an accepted NTP response
before ignored-response fallback can work.
