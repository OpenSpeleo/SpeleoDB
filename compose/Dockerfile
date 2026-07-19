FROM python:3.14.6-bookworm

ARG BUILD_ENVIRONMENT=local
ARG APP_HOME=/app

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV BUILD_ENV=${BUILD_ENVIRONMENT}

WORKDIR ${APP_HOME}

# devcontainer dependencies and utils
RUN apt-get update && apt-get install -y \
    sudo \
    git \
    bash-completion \
    ca-certificates \
    curl \
    wget \
    vim \
    ssh \
    make \
    gcc \
    # cleaning up unused files
    && apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false \
    && rm -rf /var/lib/apt/lists/*

# Install required system dependencies
RUN apt-get update && apt-get install --no-install-recommends -y \
    # psycopg dependencies
    libpq-dev \
    # Translations dependencies
    gettext \
    # Automatic Reloads
    watchman \
    # FFMPEG for video processing
    ffmpeg \
    # cleaning up unused files
    && apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false \
    && rm -rf /var/lib/apt/lists/*

# Install NodeJS
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get update && apt-get install --no-install-recommends -y \
    nodejs \
    # cleaning up unused files
    && apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false \
    && rm -rf /var/lib/apt/lists/* && \
    # update npm to latest
    npm install -g npm && npm cache clean --force

# Install uv.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# The standalone image remains Rust-free. The monorepo devcontainer enables
# this layer because it develops the local PyO3-backed openspeleo_core package.
# Keep it before the Python dependency layer so changing application
# dependencies does not invalidate the comparatively expensive toolchain.
ARG DOCKER_INCLUDE_MONOREPO_RUST_TOOLCHAIN=0
ENV RUSTUP_HOME=/usr/local/rustup
ENV CARGO_HOME=/usr/local/cargo
ENV PATH="/usr/local/cargo/bin:${PATH}"
RUN if [ "${DOCKER_INCLUDE_MONOREPO_RUST_TOOLCHAIN}" = "1" ]; then \
    curl --proto '=https' --tlsv1.2 -sSf \
        https://sh.rustup.rs -o /tmp/rustup-init.sh \
    && sh /tmp/rustup-init.sh \
        -y \
        --no-modify-path \
        --profile minimal \
        --default-toolchain stable \
    && rm /tmp/rustup-init.sh \
    && chmod -R a+rX "${CARGO_HOME}" "${RUSTUP_HOME}"; \
    fi

# UV settings
ENV VIRTUAL_ENV="/opt/speleodb-venv"
ENV UV_PROJECT_ENVIRONMENT="${VIRTUAL_ENV}"
ENV UV_LINK_MODE=copy
ENV UV_COMPILE_BYTECODE=1
ENV UV_PYTHON_DOWNLOADS=0
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"

# Install Project Dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=.workdir/test_wheels/,target=.workdir/test_wheels/ \
    uv sync --frozen --extra ${BUILD_ENV}

COPY ./compose/entrypoint /entrypoint
RUN sed -i 's/\r$//g' /entrypoint
RUN chmod +x /entrypoint

COPY ./compose/start /start
RUN sed -i 's/\r$//g' /start
RUN chmod +x /start

COPY ./compose/celery/worker/start /start-celeryworker
RUN sed -i 's/\r$//g' /start-celeryworker
RUN chmod +x /start-celeryworker

COPY ./compose/celery/beat/start /start-celerybeat
RUN sed -i 's/\r$//g' /start-celerybeat
RUN chmod +x /start-celerybeat

COPY ./compose/celery/flower/start /start-flower
RUN sed -i 's/\r$//g' /start-flower
RUN chmod +x /start-flower

# Create devcontainer user and add it to sudoers
RUN groupadd --gid 1000 dev-user \
    && useradd --uid 1000 --gid dev-user --shell /bin/bash --create-home dev-user \
    && echo dev-user ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/dev-user \
    && chmod 0440 /etc/sudoers.d/dev-user \
    && chown -R dev-user:dev-user "${VIRTUAL_ENV}"

# copy application code to WORKDIR
COPY . ${APP_HOME}

# UV settings
ENV UV_CACHE_DIR=/app/.uv/cache

ENTRYPOINT ["/entrypoint"]
