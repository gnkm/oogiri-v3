# Cloud Agent のベース VM。リポジトリ本体は COPY しない（Cursor が checkout する）。
# Cloud Agents は Ubuntu + ubuntu ユーザーを想定する。
# uv は公式イメージからバイナリだけ取り込む。
# https://docs.astral.sh/uv/guides/integration/docker/
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    UV_PYTHON_INSTALL_DIR=/opt/uv/python \
    PATH="/usr/local/bin:${PATH}"

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
    && chmod 0440 /etc/sudoers.d/ubuntu \
    && mkdir -p /opt/uv/python \
    && chown -R ubuntu:ubuntu /opt/uv

COPY --from=ghcr.io/astral-sh/uv:0.12.13 /uv /uvx /usr/local/bin/

USER ubuntu
WORKDIR /home/ubuntu

RUN uv python install 3.13
