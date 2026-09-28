# syntax=docker/dockerfile:1.8
ARG PYTHON_BASE=python@sha256:afd91e25d0d1b40e4c92bf716154ec3c4a9f0de1ce2a5c3663007fb6918eaf9c
ARG UV_BASE=ghcr.io/astral-sh/uv:0.11.6-python3.13-trixie@sha256:b3c543b6c4f23a5f2df22866bd7857e5d304b67a564f4feab6ac22044dde719b

FROM ${UV_BASE} AS uv_source
FROM ${PYTHON_BASE} AS builder

ARG HERMES_SOURCE_COMMIT=fcbd1076a93841fa88855acce810e342a5b78101
ARG HERMES_PYPROJECT_SHA256=f2d8625df7b015c52a7940ac9f6dd51cc89e70ca13548511fb4f293c90926d99
ARG HERMES_UV_LOCK_SHA256=a4f6314bf9cbfcd513c380b0d2a04e49329dca7738e9ee5b2dc1abdaf954f5f6
ARG HOST_TLS_CA_SHA256

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_MODIFY_PATH=1 \
    UV_NATIVE_TLS=true \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/hermes-venv \
    VIRTUAL_ENV=/opt/hermes-venv \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

COPY --from=uv_source /usr/local/bin/uv /usr/local/bin/uv
COPY host-tls-inspection-root.crt /usr/local/share/ca-certificates/host-tls-inspection-root.crt
RUN test -n "$HOST_TLS_CA_SHA256" && \
    echo "$HOST_TLS_CA_SHA256  /usr/local/share/ca-certificates/host-tls-inspection-root.crt" | sha256sum -c - && \
    update-ca-certificates
WORKDIR /src
COPY pyproject.toml uv.lock ./
RUN printf '%s  pyproject.toml\n%s  uv.lock\n' \
      "$HERMES_PYPROJECT_SHA256" "$HERMES_UV_LOCK_SHA256" | sha256sum -c - && \
    touch README.md && \
    uv sync --frozen --no-dev --no-install-project
COPY . .
RUN test "$(cat .hermes-source-commit)" = "$HERMES_SOURCE_COMMIT" && \
    uv pip install --no-cache-dir --no-deps -e . && \
    rm -rf /opt/hermes-venv/lib/python3.13/site-packages/uvicorn* \
           /opt/hermes-venv/bin/uvicorn \
           /opt/hermes-venv/lib/python3.13/site-packages/fastapi* \
           /opt/hermes-venv/lib/python3.13/site-packages/multipart* \
           /opt/hermes-venv/lib/python3.13/site-packages/python_multipart* \
           /opt/hermes-venv/lib/python3.13/site-packages/setuptools* \
           /opt/hermes-venv/lib/python3.13/site-packages/pip* \
           /opt/hermes-venv/bin/pip*

FROM ${PYTHON_BASE} AS runtime

ARG HERMES_SOURCE_COMMIT=fcbd1076a93841fa88855acce810e342a5b78101
ARG HOST_TLS_CA_SHA256
LABEL org.opencontainers.image.title="Hermes isolated repository worker" \
      org.opencontainers.image.source="https://github.com/NousResearch/hermes-agent" \
      org.opencontainers.image.revision="$HERMES_SOURCE_COMMIT" \
      org.opencontainers.image.version="0.20.5-hardened.1" \
      org.opencontainers.image.description="CLI-only, non-root, no browser, gateway, dashboard, API server, multimedia, SSH, or Docker client"

ENV HOME=/home/hermes \
    HERMES_HOME=/home/hermes/.hermes \
    PATH=/opt/hermes-venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HERMES_DISABLE_AUTO_UPDATE=1 \
    HERMES_DISABLE_LAZY_INSTALL=1 \
    HERMES_SESSION_SOURCE=isolated-worker \
    TERMINAL_ENV=local

# git and ripgrep are the only engineering utilities added. Git's Debian
# package pulls Perl for optional porcelain helpers; the worker uses only
# built-in status/diff/add/commit operations, so Perl is forcibly removed from
# the final image after installation. No package manager is used at runtime.
RUN apt-get -o Acquire::Retries=3 update && \
    apt-get -o Acquire::Retries=3 full-upgrade -y && \
    apt-get -o Acquire::Retries=3 install -y --no-install-recommends \
      ca-certificates git ripgrep && \
    python -m pip uninstall -y setuptools msgpack || true && \
    useradd --uid 10000 --user-group --create-home --home-dir /home/hermes \
      --shell /usr/sbin/nologin hermes && \
    dpkg --purge --force-depends liberror-perl perl libperl5.40 perl-base perl-modules-5.40 || true && \
    rm -rf /usr/lib/*/perl* /usr/share/perl* /usr/bin/perl* \
           /root/.cache /var/cache/apt/* /var/lib/apt/lists/* \
           /var/lib/dpkg /var/log/dpkg.log \
           /usr/local/lib/python3.13/site-packages/setuptools* \
           /usr/local/lib/python3.13/site-packages/msgpack* \
           /usr/local/lib/python3.13/site-packages/pip* \
           /usr/local/bin/pip* && \
    mkdir -p /workspace /opt/worker && \
    chown 10000:10000 /workspace /opt/worker

COPY host-tls-inspection-root.crt /usr/local/share/ca-certificates/host-tls-inspection-root.crt
RUN test -n "$HOST_TLS_CA_SHA256" && \
    echo "$HOST_TLS_CA_SHA256  /usr/local/share/ca-certificates/host-tls-inspection-root.crt" | sha256sum -c - && \
    update-ca-certificates

COPY --from=builder --chown=10000:10000 /opt/hermes-venv /opt/hermes-venv
COPY --from=builder --chown=0:0 /src /src
COPY --chown=10000:10000 worker_entry.py /opt/worker/worker_entry.py
COPY --chown=10000:10000 egress_proxy.py /opt/worker/egress_proxy.py

WORKDIR /workspace
USER 10000:10000
ENTRYPOINT ["python", "/opt/worker/worker_entry.py"]
CMD ["audit"]

# Flatten into a package-manager-free final filesystem. This avoids retaining
# vulnerable package records from build ancestry after their runtime files
# have been removed, and prevents any package installation in the worker.
FROM scratch AS final
ARG HERMES_SOURCE_COMMIT=fcbd1076a93841fa88855acce810e342a5b78101
LABEL org.opencontainers.image.title="Hermes isolated repository worker" \
      org.opencontainers.image.source="https://github.com/NousResearch/hermes-agent" \
      org.opencontainers.image.revision="$HERMES_SOURCE_COMMIT" \
      org.opencontainers.image.version="0.20.5-hardened.1" \
      org.opencontainers.image.description="CLI-only, non-root, no browser, gateway, dashboard, API server, multimedia, SSH, Docker client, or package manager"
COPY --from=runtime / /
ENV HOME=/home/hermes \
    HERMES_HOME=/home/hermes/.hermes \
    PATH=/opt/hermes-venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HERMES_DISABLE_AUTO_UPDATE=1 \
    HERMES_DISABLE_LAZY_INSTALL=1 \
    HERMES_SESSION_SOURCE=isolated-worker \
    TERMINAL_ENV=local
WORKDIR /workspace
USER 10000:10000
ENTRYPOINT ["python", "/opt/worker/worker_entry.py"]
CMD ["audit"]
