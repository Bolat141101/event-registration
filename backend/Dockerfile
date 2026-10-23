FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258 AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock \
    && useradd --create-home --uid 10001 app
COPY pyproject.toml alembic.ini ./
COPY app ./app
COPY migrations ./migrations
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]

FROM runtime AS test
USER root
COPY requirements-dev.lock ./
RUN pip install --no-cache-dir -r requirements-dev.lock
COPY tests ./tests
ENV PYTEST_ADDOPTS="-o cache_dir=/tmp/pytest_cache" \
    RUFF_CACHE_DIR=/tmp/ruff_cache MYPY_CACHE_DIR=/tmp/mypy_cache
USER app
CMD ["pytest"]

# Only the infrastructure regression test needs psql to execute the real bootstrap.
# The Core runtime and its ordinary test image do not include this administrative client.
FROM test AS bootstrap-test
USER root
# Only cross-service tests load the independent Notifications sender.
COPY --from=notifications /requirements.lock /tmp/notifications-requirements.lock
RUN pip install --no-cache-dir -r /tmp/notifications-requirements.lock
RUN apt-get update \
    && apt-get install --no-install-recommends -y postgresql-client \
    && rm -rf /var/lib/apt/lists/*
USER app
