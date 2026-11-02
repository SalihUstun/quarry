FROM rust:1.99-slim-trixie AS build
WORKDIR /src
COPY Cargo.toml Cargo.lock ./
COPY crates crates
RUN --mount=type=cache,target=/usr/local/cargo/registry \
    --mount=type=cache,target=/src/target \
    cargo build --release --locked -p quarry-worker \
    && cp target/release/quarry-worker /usr/local/bin/quarry-worker

FROM debian:trixie-slim AS runtime
ARG PDFIUM_RELEASE=chromium/8111
ARG TARGETARCH
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && case "$TARGETARCH" in arm64) PDFIUM_ARCH=arm64 ;; *) PDFIUM_ARCH=x64 ;; esac \
    && mkdir -p /opt/pdfium \
    && curl -fsSL "https://github.com/bblanchon/pdfium-binaries/releases/download/${PDFIUM_RELEASE}/pdfium-linux-${PDFIUM_ARCH}.tgz" \
       | tar -xz -C /opt/pdfium \
    && apt-get purge -y curl \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /usr/local/bin/quarry-worker /usr/local/bin/quarry-worker
ENV PDFIUM_LIBRARY_DIR=/opt/pdfium/lib
USER 10001
ENTRYPOINT ["quarry-worker"]
