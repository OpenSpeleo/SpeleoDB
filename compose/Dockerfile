# syntax=docker/dockerfile:1
FROM nixos/nix:2.35.2 AS nix-base
ARG TARGETARCH
RUN cp -L /etc/nix/nix.conf /tmp/nix.conf \
    && printf '%s\n' 'experimental-features = nix-command flakes read-only-local-store' \
      'sandbox = false' 'filter-syscalls = false' >> /tmp/nix.conf \
    && mv /tmp/nix.conf /etc/nix/nix.conf

FROM nix-base AS flake
WORKDIR /opt/flake
COPY flake.nix flake.lock .node-version ./

# Seed the writable cache from the base image so /nix still contains Nix itself.
# Bump the cache generation when upgrading the pinned base image.
FROM flake AS runtime-tools
RUN --mount=type=cache,id=speleodb-nix-v1-${TARGETARCH},target=/nix,from=nix-base,source=/nix,sharing=locked \
    XDG_CACHE_HOME=/nix/var/cache nix build --no-update-lock-file .#runtime -o /opt/runtime \
    && nix copy --no-check-sigs --to /closure /opt/runtime \
    && readlink /opt/runtime > /closure/profile-path

# Import packages into the image; runtime containers do not need the build cache.
FROM flake AS runtime
RUN --mount=type=bind,from=runtime-tools,source=/closure,target=/closure \
    nix copy --no-check-sigs --from 'local?root=/closure&read-only=true' "$(cat /closure/profile-path)" \
    && ln -s "$(cat /closure/profile-path)" /opt/runtime \
    && ln -s /opt/runtime/bin/bash /bin/bash \
    && ln -sf /opt/runtime/bin/bash /bin/sh

ENV PATH="/opt/speleodb-venv/bin:/usr/local/bin:/opt/runtime/bin:/nix/var/nix/profiles/default/bin:/bin:/usr/bin"
# Native Python wheels need these libraries. Never put glibc on this path.
ENV LD_LIBRARY_PATH=/opt/runtime/lib
ENV VIRTUAL_ENV=/opt/speleodb-venv
ENV UV_PROJECT_ENVIRONMENT=/opt/speleodb-venv
ENV UV_PYTHON=/opt/runtime/bin/python3.14
ENV UV_PYTHON_DOWNLOADS=never
ENV UV_LINK_MODE=copy
ENV UV_COMPILE_BYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

FROM flake AS development-tools
ARG DOCKER_INCLUDE_MONOREPO_RUST_TOOLCHAIN=0
RUN --mount=type=cache,id=speleodb-nix-v1-${TARGETARCH},target=/nix,from=nix-base,source=/nix,sharing=locked \
    if [ "$DOCKER_INCLUDE_MONOREPO_RUST_TOOLCHAIN" = 1 ]; then \
      nix_environment=monorepo; \
    else \
      nix_environment=development; \
    fi \
    && XDG_CACHE_HOME=/nix/var/cache nix build --no-update-lock-file "/opt/flake#$nix_environment" -o /opt/development \
    && nix copy --no-check-sigs --to /closure /opt/development \
    && readlink /opt/development > /closure/profile-path

FROM runtime AS build
RUN --mount=type=bind,from=development-tools,source=/closure,target=/closure \
    nix copy --no-check-sigs --from 'local?root=/closure&read-only=true' "$(cat /closure/profile-path)" \
    && ln -s "$(cat /closure/profile-path)" /opt/development
ENV PATH="/opt/speleodb-venv/bin:/usr/local/bin:/opt/development/bin:/opt/runtime/bin:/nix/var/nix/profiles/default/bin:/bin:/usr/bin"
COPY pyproject.toml uv.lock ./

FROM build AS development
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --extra local

# Preserve the devcontainer user and passwordless sudo.
RUN for account_file in passwd group shadow; do \
      cp -L --preserve=mode /etc/$account_file /tmp/$account_file \
      && mv /tmp/$account_file /etc/$account_file; \
    done \
    && groupadd --gid 1000 dev-user \
    && useradd --uid 1000 --gid dev-user --shell /bin/bash --create-home dev-user \
    && mkdir -p /usr/local/bin /etc/pam.d /run/sudo /var/db/sudo \
    && cp /opt/development/bin/sudo /usr/local/bin/sudo \
    && chmod 4755 /usr/local/bin/sudo \
    && printf '%s\n' 'root ALL=(ALL) ALL' 'dev-user ALL=(root) NOPASSWD:ALL' \
      'Defaults secure_path="/opt/speleodb-venv/bin:/usr/local/bin:/opt/development/bin:/opt/runtime/bin:/bin:/usr/bin"' > /etc/sudoers \
    && chmod 0440 /etc/sudoers \
    && printf '%s\n' 'account required /opt/development/lib/security/pam_permit.so' \
      'session required /opt/development/lib/security/pam_permit.so' > /etc/pam.d/sudo \
    && chown -R dev-user:dev-user /opt/speleodb-venv

# Editor servers use the conventional Linux ELF loader supplied by nix-ld.
# VS Code's prerequisite checker also needs conventional library paths.
RUN mkdir -p /lib /lib64 /usr/lib \
    && ln -s /opt/runtime/lib/libstdc++.so.6 /usr/lib/libstdc++.so.6 \
    && ln -s /opt/development/lib/libc.so.6 /usr/lib/libc.so.6 \
    && ln -s /opt/development/libexec/nix-ld /lib64/ld-linux-x86-64.so.2 \
    && ln -s /opt/development/libexec/nix-ld /lib/ld-linux-aarch64.so.1 \
    && ln -s /opt/development/lib/ld-linux-*.so.* /opt/ld.so \
    && test -x /opt/ld.so
ENV NIX_LD=/opt/ld.so
ENV NIX_LD_LIBRARY_PATH=/opt/runtime/lib:/opt/development/lib

COPY compose/entrypoint /entrypoint
COPY compose/start /start
COPY compose/celery/worker/start /start-celeryworker
COPY compose/celery/beat/start /start-celerybeat
RUN chmod +x /entrypoint /start /start-celeryworker /start-celerybeat
COPY . /app
RUN bash /app/compose/prepare_node_modules
ENV UV_CACHE_DIR=/app/.uv/cache
ENTRYPOINT ["/entrypoint"]

FROM build AS production-build
RUN uv sync --frozen --extra production
COPY package.json package-lock.json ./
RUN npm ci
COPY . /app
RUN npm run build && rm -rf node_modules

# Railway uses the final target. Build tools stay in the build stage.
FROM runtime AS production
COPY --from=production-build /opt/speleodb-venv /opt/speleodb-venv
COPY --from=production-build /app /app
CMD ["gunicorn", "config.wsgi:application"]
