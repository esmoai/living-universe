# Optional development-only container. This is not the C kernel.
# Tag resolves to a current patch; pin an exact digest for release CI.
FROM docker.io/library/node:22-bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates build-essential clang lld python3 \
    qemu-system-x86 qemu-system-arm ovmf qemu-efi-aarch64 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /work
CMD ["sh", "scripts/check_environment.sh"]
