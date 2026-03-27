FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04

WORKDIR /app

# Disable interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# Install Python and system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 python3.11-venv python3-pip \
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
    tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/googlechrome-linux-keyring.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/googlechrome-linux-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Set Python 3.11 as default
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1 \
    && update-alternatives --install /usr/bin/pip pip /usr/bin/pip3 1

# Set display for Xvfb
ENV DISPLAY=:99

# Install PyTorch with CUDA support first
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cu121

# Install other requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Start Xvfb and run the application
CMD Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp & \
    sleep 2 && \
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload
