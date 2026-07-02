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

COPY ${SERVICE_DIR}backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir psycopg2-binary==2.9.10

COPY ${SERVICE_DIR}backend/ ./
COPY --from=frontend /frontend/dist ./static

EXPOSE 8080
ENV PORT=8080
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --timeout-keep-alive 75"]
