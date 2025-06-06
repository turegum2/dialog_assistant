# Используем официальный образ Python
FROM python:3.9-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем системные зависимости (если необходимо)
RUN apt-get update && apt-get install -y build-essential

# Копируем файлы приложения
COPY . /app

# Устанавливаем зависимости Python
RUN pip install --no-cache-dir -r requirements.txt

# Открываем порт 8080
EXPOSE 8080

# Устанавливаем переменную окружения PORT
ENV PORT 8080

# Запускаем приложение
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]