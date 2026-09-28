# Hermes Agent Installation Audit

- Official source: `https://github.com/NousResearch/hermes-agent`
- Audited release: `v2026.7.7.2` (`0.18.2`)
- Source commit: `9de9c25f620ff7f1ce0fd5457d596052d5159596`
- GitHub release tag/commit signature: verified by GitHub
- `scripts/install.ps1` SHA-256:
  `FCD1A832B813235CDF87DC902E8F12E8149B35AB3DA00417CDB194A37BAD5FBB`
- `pyproject.toml` SHA-256:
  `004344EC34D7EBA58C0D674403BBA71CCD9442751E42C9D4801CD6581B3EFDB8`

The later official `v2026.8.19` / `0.20.5` release was identified during the
audit, along with an open upstream report that its security audit still finds
vulnerable transitive dependencies. It was not installed or treated as a silent
replacement for the fully inspected release. A version must be explicitly
selected and re-audited immediately before installation.

The installer was inspected and not executed. It can modify User PATH and
environment, bootstrap uv/Python/Node/Git/ripgrep/ffmpeg, install broad Python
and npm extras, inspect Hermes `.env` values for messaging integrations, and
prepare update/service paths. Native Windows support is officially early beta.

Official security documentation states that in-process approvals, scanners,
and allowlists are not containment; whole-process OS isolation is required.
The official Windows Compose example uses `latest`, broad persistent mounts,
restart behavior, and unrestricted egress, so it is not accepted unchanged.

Installation is blocked until an OS isolation backend is available and a
dedicated capped inference credential/provider hostname is approved. Automatic
self-update, messaging, browser, gateway, dashboard, skills hub, optional
blockchain skills, service installation, and scheduled tasks must remain off.

Host readiness result: Docker Desktop is present but cannot start because its
Linux/WSL backend is absent; WSL is not installed; Windows Sandbox and Hyper-V
PowerShell tooling are unavailable. Native fallback is prohibited.

## Native bootstrap quarantine

An incomplete, previously started native bootstrap was discovered at
`C:\Users\fjone\AppData\Local\hermes`. Its log shows that an unpinned desktop
installer from `main` installed only `uv`, detected existing Python/Git/Node,
and failed while attempting prerequisite setup. It did not create a Hermes
checkout, virtual environment, provider configuration, gateway, service, or
scheduled task. No Hermes process, credential target, environment variable,
browser extension, or shortcut was found. The stale Hermes `bin` entry was
removed from User PATH.

The directory was moved intact, not deleted, to the recoverable quarantine:
`C:\Users\fjone\CodexBackups\HermesQuarantine\native-partial-20260824-180558`.
`QUARANTINE_MANIFEST.json` records all five original files and their hashes.
The bootstrap log SHA-256 is
`F52B1621F2A67F488BAFECF927EA11896B2E175B05D76E1C4E3ABD32BCA97F32`.

## Pre-reboot checkpoint — 2026-08-24

- Owner repository: clean `main` at
  `d5fa4078f6ae8c11dc96041a82bbaad9d5af5f65`.
- Isolated clone: clean `hermes/recorder-unattended-reliability` at the same
  commit.
- Recorder process: none found before the feature change.
- `btc_forward_archive_2`: `STOPPED`; all five manifest SHA-256 values matched;
  every stream has `gap_count: 0`; no temporary files were present.
- Archive contents were not altered.
- Host: Windows 10 Pro 25H2, build 26200.9168, AMD64.
- Docker CLI: 29.6.2; daemon stopped; Docker autostart disabled.
- Docker settings did not expose a TCP daemon. Docker AI was enabled in the
  existing desktop settings and must be disabled before the isolated worker is
  allowed to run.
- WSL was unavailable before the change.
- Only `Microsoft-Windows-Subsystem-Linux` and `VirtualMachinePlatform` were
  enabled through elevated DISM commands using `/norestart`; both commands
  returned success.
- No distribution, container, Hermes package, provider, credential, service,
  scheduled task, or startup automation was installed.

After the single reboot, reopen the same Codex task and request: `resume Hermes
post-reboot setup`. The continuation must verify WSL/virtualization first,
install one minimal WSL2 distribution and use Docker's Linux backend, re-audit
and pin the selected official Hermes image by full digest, disable Docker AI
and automatic updates, then build the restricted non-root container boundary.
It must pause for owner-completed Nous Portal OAuth before any provider smoke
test.

## Post-reboot verification and release gate — 2026-08-24

- The Windows optional-feature and hardware probe passed: WSL, Virtual Machine
  Platform, firmware virtualization, and SLAT are enabled.
- The official Microsoft WSL application/kernel package was installed without
  a user distribution: WSL `2.7.12.0`, kernel `6.18.33.2-2`, default version 2.
- Docker Desktop `4.84.0` successfully used its WSL2 Linux engine. The server
  was Engine `29.6.2`, Linux/amd64, with seccomp, cgroup v2, memory limits,
  CPU limits, and PID limits available.
- Only Docker's managed `docker-desktop` WSL distribution was required; no
  general-purpose Linux distribution was installed.
- No unauthenticated Docker listener existed on TCP 2375 or 2376. Docker AI,
  Docker Model Runner, update checks, module auto-updates, and login autostart
  were disabled. Existing per-user Docker settings were changed accordingly.
- The official release list was rechecked immediately before selection. Latest
  stable was `v2026.8.19` / `0.20.5`, signed-tag target
  `fcbd1076a93841fa88855acce810e342a5b78101`.
- `pyproject.toml` SHA-256:
  `F2D8625DF7B015C52A7940AC9F6DD51CC89E70CA13548511FB4F293C90926D99`.
- `uv.lock` SHA-256:
  `A4F6314BF9CBFCD513C380B0D2A04E49329DCA7738E9EE5B2DC1ABDAF954F5F6`.
- Official multi-platform image index digest:
  `sha256:3811ed13da874fba2ac99b6d492db9a203d34cb6dccf90d886948c00d0ccec09`.
- Selected Linux/amd64 manifest digest:
  `sha256:f3cba6abf5ed80d47a271498d663ace5dda87f45000552afb8be8370a35df1b5`.
  The manifest includes an attestation descriptor and was downloaded by digest
  for inspection only.

The local Docker Scout gate indexed 2,080 packages and found 49 high-or-worse
vulnerabilities across 13 packages: **5 critical and 44 high**. Findings
included vulnerable Go stdlib, Perl, npm tar, Debian docker.io, cJSON,
brace-expansion, quick-xml, quinn-proto, ip-address, libssh, rustls-webpki,
nanoid, and undici packages. Multiple findings have published fixed versions;
two critical Perl findings were reported without a fix. This does not satisfy
the owner's release-security gate.

No Hermes container was created or run; `docker ps --all` was empty. No Hermes
home, provider configuration, OAuth token, gateway, service, schedule, startup
automation, or engineering task was created. Docker Desktop was stopped after
the failed gate. The pulled image remains in Docker's local content store as
evidence/cache and has not been executed.

Status: `BLOCKED_RELEASE_SECURITY_GATE`. A future continuation requires a new
official release/image whose pinned digest passes a fresh dependency and image
scan, or a separate explicit owner acceptance of enumerated residual risks.
The current authorization does not permit such risk acceptance, rebuilding an
unofficial derivative image, or bypassing this gate.

Rollback facts: WSL can be removed later through Microsoft's supported WSL
uninstall procedure and the two optional features can be disabled with DISM;
Docker settings can be restored by changing `DisableUpdate`,
`SilentModulesUpdate`, and `EnableDockerAI`. No rollback was performed because
the owner authorized WSL2/Docker and the changes are not harmful by themselves.

## Owner-approved hardened derivative — 2026-08-25 UTC

The owner subsequently authorized a minimal custom worker built from the same
verified official source commit. No cached official image was executed.

- Official source: `v2026.8.19`, commit
  `fcbd1076a93841fa88855acce810e342a5b78101`, Hermes `0.20.5`.
- Base index: `python:3.13-slim-trixie` at
  `sha256:afd91e25d0d1b40e4c92bf716154ec3c4a9f0de1ce2a5c3663007fb6918eaf9c`.
- UV build stage: `0.11.6-python3.13-trixie` at
  `sha256:b3c543b6c4f23a5f2df22866bd7857e5d304b67a564f4feab6ac22044dde719b`.
- Host TLS inspection root was explicitly identified as Norton Web/Mail Shield,
  thumbprint `ABECF5D7EC8D3B1B42CE1BEFC2631B6EE8684024`, exported public-certificate
  SHA-256 `93b1a069f74bb0cd13123a8007ea8e7483cf30b81205cbf88559f0a14d57c1af`.
  TLS verification was never disabled.
- Final image: `hermes-worker-hardened:0.20.5-fcbd1076`, immutable local digest
  `sha256:dc5be3921388b07817ee93292841e0025ecda1b5c28471fd9d6515da902c214e`,
  122,744,027 bytes.

The initial base scan found 2 CRITICAL and 5 HIGH findings: Perl
`CVE-2026-13221`, `CVE-2026-12087`, `CVE-2026-48959`, and `CVE-2026-48962`;
msgpack `GHSA-6v7p-g79w-8964` / `CVE-2026-57585`; and setuptools
`CVE-2025-47273`. Perl, pip, package-manager metadata, and server entry points
were removed in a package-manager-free scratch final stage. The msgpack and
setuptools findings were traced to pip's embedded `bom.cdx.json`, not installed
runtime packages; removing pip eliminated the scanner evidence. The final
unsuppressed Docker Scout scan indexed 69 packages and reported **0 CRITICAL,
0 HIGH, 0 MEDIUM, and 0 LOW**. No finding was suppressed or accepted.

The image has no Perl, pip, Docker CLI/socket, SSH client, Node/npm, FFmpeg, or
Chromium. It includes no web, dashboard, API-server, messaging-gateway, native,
cron, optional MCP/skill, documentation, evaluation, or test source trees. Its
only callable entry commands are `audit` and `task <workspace-prompt>`; task
mode enables only Hermes `terminal` and `file` toolsets.

Containment audit passed with UID/GID 10000, read-only root filesystem, all
capabilities dropped, `no-new-privileges`, 2 CPUs, 4 GiB RAM/swap, 128 PIDs,
restart `no`, no ports, and only the sanitized clone mounted at `/workspace`.
The clone is on `hermes/recorder-unattended-reliability` at
`8f1ce7b3e923764858dbf004e9de452e9c113547` and has no Git remote. A network-none
audit passed. An internal-network proxy test allowed only
`portal.nousresearch.com:443` and denied `example.com:443`, with both attempts
logged.

No OAuth was started, no credential was requested, no inference call occurred,
and provider usage/cost is exactly zero. The Hermes agent loop and required
smoke task were not run because no dedicated provider credential with an
independently verified token/cost cap has been provisioned. The external
launcher enforces wall-clock, filesystem, process/failure, CPU, RAM, and PID
budgets, but an authoritative provider-side token/cost cap is still required.

Status: `BLOCKED_DEDICATED_PROVIDER_BUDGET`. The first overnight assignment is
not ready. Do not run `-Mode smoke` until the owner provisions a dedicated
credential, records the exact inference hostname, and verifies a provider-side
hard spending/token limit. Passing that gate authorizes only the harmless smoke
test, not the overnight engineering program.
