FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Install the Chromium browser + its OS-level dependencies for Playwright.
# Without this the ingestion pipeline builds fine but fails at runtime the
# moment it tries to launch a browser inside the container.
RUN python -m playwright install --with-deps chromium

# Copy application source code and migrations
COPY src/ /app/src/
COPY alembic/ /app/alembic/
COPY alembic.ini /app/
COPY scripts/ /app/scripts/
COPY tests/ /app/tests/
COPY .env.example /app/.env

# Create data directories
RUN mkdir -p /app/data/raw_html /app/data/reports /app/data/temp

EXPOSE 8000 8501

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
