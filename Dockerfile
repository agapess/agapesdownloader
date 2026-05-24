FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install yt-dlp
RUN curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp \
    -o /usr/local/bin/yt-dlp && chmod +x /usr/local/bin/yt-dlp

WORKDIR /app

# Install Python deps before copying app code (layer cache)
COPY pyproject.toml ./
RUN pip install --no-cache-dir \
    flask \
    gunicorn \
    python-telegram-bot

# Copy app
COPY . .

# Downloads volume
RUN mkdir -p /app/downloads
VOLUME ["/app/downloads"]

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "120", "main:app"]
