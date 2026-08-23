# TaskBoard Demo devcontainer
#
# A self-contained Linux environment for the "Claude Code + Semgrep auto-scan"
# demo. Ships Claude Code, the Semgrep Guardian plugin and the Semgrep CLI so
# the only thing the host has to provide at runtime is credentials:
#   - ~/.semgrep       bind-mounted (Guardian OIDC token)
#   - ~/.claude        named volume (Claude Code login, persists across runs)
#
# Base images are pinned by digest -- tags are mutable. Digest-only (no
# `tag@sha256:`) is deliberate: the devcontainer CLI rejects the combined form
# when it inspects the base image, so the readable version goes in a comment.
# Dockerfiles have no trailing comments, hence the comment-above style.
#
# ghcr.io/astral-sh/uv:0.10.0
FROM ghcr.io/astral-sh/uv@sha256:78a7ff97cd27b7124a5f3c2aefe146170793c56a1e03321dd31a289f6d82a04f AS uv
# mcr.microsoft.com/devcontainers/base:ubuntu-24.04
FROM mcr.microsoft.com/devcontainers/base@sha256:d94c97dd9cacf183d0a6fd12a8e87b526e9e928307674ae9c94139139c0c6eae

ARG TZ
ENV TZ="$TZ"

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# python3 is NOT in devcontainers/base -- prereq.py, reset.py and the
# postStartCommand all need it, so install it explicitly rather than assume.
# tmux drives the prompt pre-fill.
RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 \
      tmux \
      jq \
      ripgrep \
      less \
      sqlite3 \
  && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY --from=uv /uv /usr/local/bin/uv

# /opt and /workspace are root-owned in the base image; the vscode user needs to
# write to both (build-time plugin seed, runtime bind mount).
RUN mkdir -p /opt/claude-seed /workspace && chown vscode:vscode /opt/claude-seed /workspace

ENV DEVCONTAINER=true
ENV EDITOR=nano
ENV VISUAL=nano

# tmux picks its UTF-8 mode from LC_ALL/LC_CTYPE/LANG. With none of them set it
# runs the client in 8-bit mode and replaces every character it cannot emit with
# "_", which turns the Claude Code banner and its status-line glyphs into rows of
# underscores. The base image ships C.utf8, it just never selects it.
ENV LANG=C.UTF-8

USER vscode
ENV PATH="/home/vscode/.local/bin:$PATH"

# Claude Code (native installer -- no Node toolchain needed)
RUN curl -fsSL https://claude.ai/install.sh | bash

# Semgrep CLI. prereq.py checks for it, and it is handy for manual scans during
# the demo; the Guardian hook itself ships a self-contained linux binary.
RUN uv tool install semgrep

# Bake a pristine Claude config -- marketplace registration plus the Semgrep
# Guardian plugin -- into /opt/claude-seed. At runtime a named volume is mounted
# over ~/.claude (so the login survives between demos), and post_create.py syncs
# anything missing out of this seed. Keeping the seed separate from ~/.claude
# means a rebuilt image still delivers a newer plugin to an existing volume.
ENV CLAUDE_SEED_DIR=/opt/claude-seed
RUN CLAUDE_CONFIG_DIR="$CLAUDE_SEED_DIR" claude plugin marketplace add anthropics/claude-plugins-official && \
    CLAUDE_CONFIG_DIR="$CLAUDE_SEED_DIR" claude plugin install semgrep@claude-plugins-official --scope user --yes

COPY --chown=vscode:vscode post_create.py /opt/post_create.py

WORKDIR /workspace
