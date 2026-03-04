# ── VBD-Copilot ───────────────────────────────────────────────────────────────
# Standalone container for running the TUI app.
#
#   docker build -t vbd-copilot .
#   docker run -it --rm \
#     -v ~/.copilot:/home/app/.copilot \
#     -v $(pwd)/outputs:/app/outputs \
#     vbd-copilot
# ──────────────────────────────────────────────────────────────────────────────

FROM python:3.12-slim AS base

# ── System dependencies ──────────────────────────────────────────────────────
# libreoffice-impress  - PPTX-to-PDF conversion for QA
# poppler-utils        - PDF-to-image conversion for visual QA
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libreoffice-impress \
        poppler-utils \
        git \
    && rm -rf /var/lib/apt/lists/*

# ── Non-root user ────────────────────────────────────────────────────────────
RUN useradd -m -s /bin/bash app
WORKDIR /app

# ── Python dependencies ──────────────────────────────────────────────────────
COPY pyproject.toml ./
RUN pip install --no-cache-dir . 2>/dev/null || true
# Full install once source is available (pyproject needs the modules present)
COPY . .
RUN pip install --no-cache-dir .

# ── Ensure output dirs exist ─────────────────────────────────────────────────
RUN mkdir -p outputs/slides outputs/demos plans && \
    chown -R app:app /app

USER app

# ── Mount points ─────────────────────────────────────────────────────────────
# ~/.copilot  -> /home/app/.copilot  (auth tokens - read-only is fine)
# ./outputs   -> /app/outputs        (generated files persist on host)
VOLUME ["/home/app/.copilot", "/app/outputs"]

# ── Entrypoint ───────────────────────────────────────────────────────────────
ENV PYTHONUNBUFFERED=1
CMD ["python", "app.py"]
