# Cloud Agent のベース VM。リポジトリ本体は COPY しない（Cursor が checkout する）。
# Docker Hub の ubuntu:24.04 は Cloud 上で layer 取得が切れることがあるため、
# ベースは ghcr.io の公式 uv イメージにする（Debian trixie + uv + Python 3.13）。
# https://docs.astral.sh/uv/guides/integration/docker/
FROM ghcr.io/astral-sh/uv:0.12.13-python3.13-trixie-slim

ENV DEBIAN_FRONTEND=noninteractive

# exec-daemon 用に curl、hooks 用に jq。
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        jq \
        sudo \
    && rm -rf /var/lib/apt/lists/* \
    && if ! id -u ubuntu >/dev/null 2>&1; then useradd -m -s /bin/bash ubuntu; fi \
    && echo 'ubuntu ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/ubuntu \
    && chmod 0440 /etc/sudoers.d/ubuntu

USER ubuntu
WORKDIR /home/ubuntu
