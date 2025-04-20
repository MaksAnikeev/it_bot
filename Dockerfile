FROM python:3.11-slim

RUN apt-get update && apt-get install -y nano postgresql-client curl

# Устанавливаем переменные окружения
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем зависимости для psycopg2 и других библиотек
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Копируем только необходимые файлы
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем остальной код
COPY . .

# Указываем точку входа (опционально, будет переопределён в docker-compose)
CMD ["gunicorn", "-b", "0.0.0.0:8080", "it_tg_bot.wsgi", "--reload"]