# стабильная версия Python
FROM python:3.11-slim

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Устанавливаем python зависимости
COPY .requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код
COPY . .

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]



