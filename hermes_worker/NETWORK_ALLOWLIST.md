# Runtime Network Allowlist

Default: deny all. DNS alone does not authorize a destination.

The final inference-provider host is intentionally unset until the owner
supplies a dedicated, capped, non-trading credential. At runtime, only that
documented HTTPS inference hostname may be permitted. Public recorder behavior
must be tested with mocks; the first overnight task does not require live
Hyperliquid access.

Setup-only destinations, not runtime destinations:

- `github.com/NousResearch/hermes-agent` — official source/tag verification
- `registry-1.docker.io` / Docker Hub content delivery — pinned official image
- `ghcr.io/astral-sh/uv` — digest-pinned UV build stage
- `deb.debian.org` / `debian-security` — build-stage patched OS packages
- `pypi.org` / `files.pythonhosted.org` — hashes locked by official `uv.lock`

Runtime enforcement uses an internal Docker network. The worker has no route
to the default bridge. A separate non-root CONNECT proxy joins both networks,
allows only one exact owner-approved inference hostname on TCP 443, rejects IP
literals and non-global DNS answers, and emits one JSON event for every allow,
deny, or error. The hostname remains unset until a dedicated capped credential
is provisioned. The smoke test therefore remains blocked.

No package indexes, Git hosting, web search, browser, messaging, telemetry,
plugin/skill hubs, exchange endpoints, account endpoints, or arbitrary HTTPS
destinations are allowed during an overnight task.
