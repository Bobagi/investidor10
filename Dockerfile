FROM python:3.11

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    unzip \
    curl \
    gnupg \
    ca-certificates \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpangocairo-1.0-0 \
    libxshmfence1 \
    libgtk-3-0 \
    libdrm2 \
    libxcb1 \
    libxext6 \
    libxfixes3 \
    libxrender1 \
    libx11-6 \
    fonts-liberation \
    libvulkan1 \
    xdg-utils \
  && rm -rf /var/lib/apt/lists/*

# Chrome (complete version)
ARG CHROME_URL=https://storage.googleapis.com/chrome-for-testing-public/135.0.7049.84/linux64/chrome-linux64.zip
RUN curl -sSL $CHROME_URL -o chrome.zip && \
    unzip chrome.zip -d /opt/ && \
    mv /opt/chrome-linux64 /opt/chrome && \
    rm chrome.zip && \
    ln -s /opt/chrome/chrome /usr/bin/google-chrome

# ChromeDriver
ARG CHROMEDRIVER_URL=https://storage.googleapis.com/chrome-for-testing-public/135.0.7049.84/linux64/chromedriver-linux64.zip
RUN curl -sSL $CHROMEDRIVER_URL -o chromedriver.zip && \
    unzip chromedriver.zip -d /opt/ && \
    mv /opt/chromedriver-linux64/chromedriver /usr/local/bin/ && \
    chmod +x /usr/local/bin/chromedriver && \
    rm chromedriver.zip

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN pip install --no-cache-dir gunicorn

COPY . .

ENV API_PORT=${API_PORT:-5000}

CMD ["sh","-c","gunicorn --workers 1 --timeout 3000 --bind 0.0.0.0:${API_PORT} main:app"]
