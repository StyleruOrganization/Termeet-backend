FROM python:3.14-alpine AS builder

# Python
ENV PYTHONFAULTHANDLER=1 \
  PYTHONUNBUFFERED=1 \
  PYTHONHASHSEED=random \
  # Pip
  PIP_NO_CACHE_DIR=off \
  PIP_DISABLE_PIP_VERSION_CHECK=on \
  PIP_DEFAULT_TIMEOUT=100 \
  # Poetry
  POETRY_NO_INTERACTION=1 \
  POETRY_VIRTUALENVS_CREATE=true \
  POETRY_VIRTUALENVS_IN_PROJECT=true \
  POETRY_CACHE_DIR='/var/cache/pypoetry' \
  POETRY_HOME='/usr/local' \
  POETRY_VERSION=2.3.2

RUN pip install poetry

WORKDIR /code

RUN --mount=type=bind,source=poetry.lock,target=poetry.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    poetry install --only=main --no-interaction --no-ansi


FROM python:3.14-alpine 

WORKDIR /code

COPY --from=builder /code/.venv ./.venv

ENV PATH="/code/.venv/bin:$PATH"

# Аккуратнее: переношу только backend и .env
COPY .env .
COPY backend ./backend