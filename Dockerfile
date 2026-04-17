FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY okx_futures_bot.py ./

# 默认守护运行，可通过 `-e MODE=healthcheck` 做健康检查
CMD ["python", "okx_futures_bot.py"]
