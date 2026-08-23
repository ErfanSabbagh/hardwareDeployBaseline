FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl python3 python3-pip \
    && rm -rf /var/lib/apt/lists/*

ARG CLI_VERSION=1.2.0
RUN curl -fsSL \
      "https://github.com/arduino/arduino-cli/releases/download/v${CLI_VERSION}/arduino-cli_${CLI_VERSION}_Linux_64bit.tar.gz" \
    | tar -xz -C /usr/local/bin arduino-cli

ENV ARDUINO_DIRECTORIES_DATA=/opt/arduino \
    ARDUINO_DIRECTORIES_DOWNLOADS=/opt/arduino/staging \
    ARDUINO_DIRECTORIES_USER=/opt/arduino/user

RUN arduino-cli core update-index \
    && arduino-cli core install arduino:avr \
    && arduino-cli lib install "Adafruit Unified Sensor" "DHT sensor library"

WORKDIR /app
COPY backend/requirements.txt /app/requirements.txt
RUN pip3 install --break-system-packages --no-cache-dir -r /app/requirements.txt

COPY backend/app /app/app
COPY shared /app/shared
COPY frontend /app/frontend

ENV FRONTEND_DIR=/app/frontend \
    PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
