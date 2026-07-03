# Build contexts:
# - Railway (repo root): uses default SERVICE_DIR=services/content-hub/
# - CI/local: docker build --build-arg SERVICE_DIR= ./services/content-hub

ARG SERVICE_DIR=services/content-hub/

FROM node:20-alpine AS frontend
ARG SERVICE_DIR
WORKDIR /frontend
COPY ${SERVICE_DIR}frontend/package.json ./
RUN npm install
COPY ${SERVICE_DIR}frontend/ ./
RUN npm run build

FROM python:3.11-slim
ARG SERVICE_DIR
WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV SERVE_STATIC=false

RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx gettext-base \
    && rm -rf /var/lib/apt/lists/*

COPY ${SERVICE_DIR}backend/requirements.txt .
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY ${SERVICE_DIR}backend/ ./
COPY --from=frontend /frontend/dist ./static
COPY ${SERVICE_DIR}deploy/nginx.conf.template /etc/nginx/nginx.conf.template
COPY ${SERVICE_DIR}deploy/start.sh /start.sh
RUN chmod +x /start.sh

EXPOSE 8080
ENV PORT=8080
CMD ["/start.sh"]
