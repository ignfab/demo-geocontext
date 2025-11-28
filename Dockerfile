FROM ubuntu:24.04 AS base

# Install uv / uvx
ENV UV_INSTALL_DIR=/usr/local/bin
RUN apt-get update \
 && apt-get install -y curl \
 && curl -LsSf https://astral.sh/uv/install.sh | sh \
 && rm -rf /var/lib/apt/lists*

# Configure folder for uv python installation
ENV UV_PYTHON_INSTALL_DIR=/opt/uv-python

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
COPY uv.lock pyproject.toml .python-version ./
# Install dependencies and sync
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev

# Copy static files
COPY assets ./assets
COPY pages ./pages
COPY front/dist ./front/dist
# Copy python scripts
COPY *.py .
# Copy LICENSE
COPY LICENSE .

# uid=1000,gid=1000 in ubuntu:24.04
USER ubuntu

# create dynamic folders with ubuntu as a owner
RUN mkdir -p /home/ubuntu/.cache/uv \
 && mkdir -p /home/ubuntu/.local/share/uv/tools \
 && mkdir -p /home/ubuntu/.npm

 # Gradio analytics opt-out
ENV GRADIO_ANALYTICS_ENABLED="False"

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["python", "demo_gradio.py"]
