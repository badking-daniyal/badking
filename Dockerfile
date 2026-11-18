FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8

COPY pyproject.toml README.md ./
COPY badking/ ./badking/

RUN pip install --no-cache-dir .

COPY examples/ ./examples/

CMD ["python", "examples/echo_bot.py"]
