# Cтабильная версия Python
FROM python:3.11-slim AS builder

# Системные зависимости для компиляции (psycopg2, Pillow)
RUN apt-get update && apt-get install -y \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем uv
COPY --from=ghcr.io/astral-sh/uv:0.4.9 /uv /bin/uv

# Настройки для ускорения и стабильности
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

WORKDIR /app

# Сначала копируем только файлы зависимостей
COPY uv.lock pyproject.toml ./

# Устанавливаем зависимости в виртуальное окружение /app/.venv
# --frozen гарантирует соответствие лок-файлу
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Копируем остальной код и доустанавливаем проект
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ЭТАП 2: Финальный образ (runtime)
FROM python:3.11-slim AS runtime

WORKDIR /app

# Копируем только то, что нужно для работы (без мусора от компиляции)
COPY --from=builder /app /app

# Устанавливаем системную библиотеку, нужную для работы БД в рантайме
RUN apt-get update && apt-get install -y libpq5 && rm -rf /var/lib/apt/lists/*

# Прокидываем путь к виртуальному окружению, созданному uv
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

EXPOSE 8000