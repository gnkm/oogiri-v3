# 製品コンテナ（Podman / OCI）。Cloud Agent の VM 用 `.cursor/Dockerfile` ではない。
#
# OpenRouter API キーはイメージに埋め込まない。実行時に Podman secret
# `openrouter_api_key_oogiri` をマウントする。
#
# 例:
#   podman secret create openrouter_api_key_oogiri -
#   podman build -t oogiri -f Containerfile
#   podman run --rm --secret openrouter_api_key_oogiri oogiri --help

FROM python:3.13-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.12.13 /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock README.md config.example.toml ./
RUN cp config.example.toml config.toml
COPY src ./src
COPY prompts ./prompts

RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

ENTRYPOINT ["oogiri"]
