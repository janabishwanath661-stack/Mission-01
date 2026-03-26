FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including Chrome, FFmpeg, audio libraries, and Xvfb
RUN apt-get update && apt-get install -y \
    wget curl gnupg ca-certificates \
    ffmpeg \
    libasound2 \
    fonts-liberation \
    libappindicator3-1 \
    libnss3 \
    libxss1 \
    xdg-utils \
    libgbm1 \
    xvfb \
    x11vnc \
    fluxbox \
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/googlechrome-linux-keyring.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/googlechrome-linux-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Set display for Xvfb
ENV DISPLAY=:99

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Start Xvfb and run the application
CMD Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp & \
    sleep 2 && \
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload
