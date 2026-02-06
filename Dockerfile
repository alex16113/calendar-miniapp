FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

RUN adduser --disabled-password --gecos "" appuser \
    && mkdir -p /app/data /app/runtime \
    && chown -R appuser:appuser /app

USER appuser

CMD ["python", "bot.py"]
