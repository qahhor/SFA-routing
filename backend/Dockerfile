# ==============================================
# SFA-Routing: Production Dockerfile
# ==============================================
# Multi-stage build for minimal image size (<200MB)
# Usage: docker build -t sfa-routing-api .

# ==============================================
# Stage 1: Builder
# ==============================================
FROM python:3.11-slim as builder

WORKDIR /build

# Установка build зависимостей
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Копирование и установка Python зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt

# ==============================================
# Stage 2: Runtime
# ==============================================
FROM python:3.11-slim as runtime

# Метаданные образа
LABEL maintainer="SFA-Routing Team"
LABEL version="1.1.0"
LABEL description="Route Optimization Service API"

# Переменные окружения
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    APP_HOME=/app

WORKDIR $APP_HOME

# Установка runtime зависимостей
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Копирование установленных пакетов из builder
COPY --from=builder /install /usr/local

# Создание непривилегированного пользователя
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser

# Создание необходимых директорий
RUN mkdir -p $APP_HOME/logs $APP_HOME/tmp && \
    chown -R appuser:appgroup $APP_HOME

# Копирование кода приложения
COPY --chown=appuser:appgroup . .

# Переключение на непривилегированного пользователя
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Порт
EXPOSE 8000

# Точка входа
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
