# API image for Render (or any container host).
# Serves the FastAPI app against Turso. Transcription/ingestion runs elsewhere
# (scheduled GitHub Action), so this image stays lean — no ffmpeg/audio tooling.
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Copy source (see .dockerignore — data/, frontend/, venv excluded) and install.
COPY . .
RUN pip install --upgrade pip && pip install .

EXPOSE 8000

# Render provides $PORT at runtime.
CMD ["sh", "-c", "uvicorn digest.api.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
