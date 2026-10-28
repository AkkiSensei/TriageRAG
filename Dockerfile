FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY data/ ./data/
COPY tools/ ./tools/
COPY eval/ ./eval/
COPY tests/ ./tests/

RUN pip install --no-cache-dir -e ".[api,dev]"

EXPOSE 8000

CMD ["python", "tools/tasks.py", "api", "--host", "0.0.0.0", "--port", "8000"]

