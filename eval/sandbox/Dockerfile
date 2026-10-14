# Sandbox for running real cases: the project under test and the agent's
# patch are untrusted code. Nothing from the host is mounted except the one
# case's working directory; tests run with the network off.
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates build-essential unzip \
    && rm -rf /var/lib/apt/lists/*
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && mv /root/.local/bin/uv /usr/local/bin/uv
# JavaScript cases: node 22 + corepack (pnpm/yarn) + bun.
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/* && corepack enable
RUN curl -fsSL https://bun.sh/install | bash && mv /root/.bun/bin/bun /usr/local/bin/bun
# Interpreters the repositories' eras need are fetched by uv at the install
# stage into the cache volume, so the venv's symlinks survive into the
# (network-less) run stage. pr-witness itself runs on the image's 3.11.
ENV UV_PYTHON_INSTALL_DIR=/work/.cache/uv-python UV_CACHE_DIR=/work/.cache/uv
COPY . /opt/pr-witness
RUN pip install --no-cache-dir /opt/pr-witness checkwash==0.7.0
RUN useradd -m -u 1000 runner
USER runner
ENV PR_WITNESS_REAL_CACHE=/work/.cache HOME=/home/runner
WORKDIR /work
ENTRYPOINT ["python", "/opt/pr-witness/eval/run_real.py"]
