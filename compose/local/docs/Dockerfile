FROM python:3.13

ARG BUILD_ENVIRONMENT=local
ARG APP_HOME=/app

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV BUILD_ENV=${BUILD_ENVIRONMENT}

WORKDIR ${APP_HOME}

RUN apt-get update && apt-get install --no-install-recommends -y \
  sudo \
  git \
  bash-completion \
  wget \
  curl \
  vim \
  ssh \
  make \
  gcc \
  # To run the Makefile
  make \
  # psycopg dependencies
  libpq-dev \
  # Translations dependencies
  gettext \
  # Uncomment below lines to enable Sphinx output to latex and pdf
  # texlive-latex-recommended \
  # texlive-fonts-recommended \
  # texlive-latex-extra \
  # latexmk \
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

COPY ./compose/local/docs/start /start-docs
RUN sed -i 's/\r$//g' /start-docs
RUN chmod +x /start-docs

WORKDIR /docs
