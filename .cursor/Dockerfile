# Cloud Agent のベース VM。リポジトリ本体は COPY しない（Cursor が checkout する）。
# 公式 derived image: uv + Python 3.13（Debian trixie）
# https://docs.astral.sh/uv/guides/integration/docker/
FROM ghcr.io/astral-sh/uv:python3.13-trixie-slim

ENV DEBIAN_FRONTEND=noninteractive

# hooks（jq）と git 用。uv / Python はベースイメージに含まれる。
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
        jq \
    && rm -rf /var/lib/apt/lists/*
