FROM ubuntu:24.04 AS base

# Install uv / uvx
ENV UV_INSTALL_DIR=/usr/local/bin
RUN apt-get update \
 && apt-get install -y curl \
 && curl -LsSf https://astral.sh/uv/install.sh | sh \
 && rm -rf /var/lib/apt/lists*

# Install NodeJS (npx)
RUN apt-get update \
 && apt-get install -y ca-certificates curl gnupg \
 && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
 && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list \
 && apt-get update \
 && apt-get install -y nodejs \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
# Copy application files only
COPY uv.lock pyproject.toml .python-version .
# Install dependencies and sync
RUN uv sync --no-cache --no-dev

COPY front/dist ./front/dist
COPY *.py .
COPY LICENSE .


EXPOSE 8000
CMD ["uv", "run", "demo_gradio.py"]
