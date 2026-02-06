# Stage 1: сборка Mini App (Vite/React)
FROM node:20-alpine AS frontend-build
WORKDIR /build
COPY mini-app/package.json mini-app/package-lock.json ./
RUN npm ci
COPY mini-app/ ./
RUN npm run build

# Stage 2: бот + FastAPI + статика
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY api/ api/
COPY database/ database/
COPY handlers/ handlers/
COPY services/ services/
COPY middlewares/ middlewares/
COPY scripts/ scripts/
COPY app_context.py bot.py config.py logging_context.py logging_setup.py run.py ./
COPY --from=frontend-build /build/dist ./dist

RUN adduser --disabled-password --gecos "" appuser \
    && mkdir -p /app/data /app/runtime \
    && chown -R appuser:appuser /app

USER appuser

# Один процесс: бот (в фоне) + uvicorn на 8000. Volume для БД/OAuth: монтировать /app/data
EXPOSE 8000
CMD ["python", "run.py"]
