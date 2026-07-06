# Container for the live WhatsApp Digital FTE webhook (Cloud Run).
FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (better layer caching).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the app (secrets/.env are excluded via .gcloudignore — env vars come from Cloud Run).
COPY . .

# Cloud Run provides $PORT (default 8080). Bind uvicorn to it.
ENV PORT=8080
CMD exec uvicorn whatsapp_webhook.main:app --host 0.0.0.0 --port $PORT
