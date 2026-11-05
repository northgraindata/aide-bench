FROM python:3.12.7-slim-bookworm
RUN apt-get update \
 && apt-get install -y --no-install-recommends git \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/aide-bench
# Third-party dependencies are pinned in requirements.lock (regenerate: uv lock && uv export --no-hashes --no-emit-project --no-dev --frozen -o requirements.lock)
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir --no-deps .
