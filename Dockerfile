# ForeverYours - Voice Companion for Seniors
# Container deployment for Nebius AI Cloud compute / Hugging Face Spaces / cloud hosting
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=7860

# Install system dependencies required for speech synthesis (espeak-ng for pyttsx3) and audio processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    espeak-ng \
    libespeak-dev \
    ffmpeg \
    alsa-utils \
    libsndfile1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code and bundled audio samples
COPY . .

# Ensure data and output directories exist
RUN mkdir -p data out/audio

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:7860/ || exit 1

CMD ["python", "webapp.py"]
