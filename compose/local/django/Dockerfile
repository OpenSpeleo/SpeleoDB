FROM python:3.13

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
    wget \
    curl \
    vim \
    ssh \
    make \
    gcc \
    # cleaning up unused files
    && apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false \
    && rm -rf /var/lib/apt/lists/*

# Install Rust & Cargo for `watchfiles` dependency
RUN curl https://sh.rustup.rs -sSf | \
    sh -s -- --default-toolchain stable -y

ENV PATH=/root/.cargo/bin:$PATH

# Install required system dependencies
RUN apt-get update && apt-get install --no-install-recommends -y \
    # psycopg dependencies
    libpq-dev \
    # Translations dependencies
    gettext \
    # cleaning up unused files
    && apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false \
    && rm -rf /var/lib/apt/lists/*

# Install uv.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# UV settings
ENV UV_MOUNT_CACHE_DIR=/tmp/.cache
ENV UV_CACHE_DIR=${UV_MOUNT_CACHE_DIR}/cache
# Use the system Python environment
ENV UV_PROJECT_ENVIRONMENT="/usr/local/"
ENV UV_LINK_MODE=copy

# Install Project Dependencies
COPY pyproject.toml .
COPY uv.lock .
RUN --mount=type=bind,source=.uv,target=${UV_MOUNT_CACHE_DIR},readonly=false \
    uv sync --frozen --extra ${BUILD_ENV}

COPY ./compose/production/django/entrypoint /entrypoint
RUN sed -i 's/\r$//g' /entrypoint
RUN chmod +x /entrypoint

COPY ./compose/local/django/start /start
RUN sed -i 's/\r$//g' /start
RUN chmod +x /start

COPY ./compose/local/django/celery/worker/start /start-celeryworker
RUN sed -i 's/\r$//g' /start-celeryworker
RUN chmod +x /start-celeryworker

COPY ./compose/local/django/celery/beat/start /start-celerybeat
RUN sed -i 's/\r$//g' /start-celerybeat
RUN chmod +x /start-celerybeat

COPY ./compose/local/django/celery/flower/start /start-flower
RUN sed -i 's/\r$//g' /start-flower
RUN chmod +x /start-flower

# Create devcontainer user and add it to sudoers
RUN groupadd --gid 1000 dev-user \
    && useradd --uid 1000 --gid dev-user --shell /bin/bash --create-home dev-user \
    && echo dev-user ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/dev-user \
    && chmod 0440 /etc/sudoers.d/dev-user

# copy application code to WORKDIR
COPY . ${APP_HOME}

# UV settings
ENV UV_CACHE_DIR=/app/.uv/cache

ENTRYPOINT ["/entrypoint"]
