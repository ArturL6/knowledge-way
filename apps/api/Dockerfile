FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv==0.12.3 && uv sync --frozen --no-dev --no-install-project
COPY . .
WORKDIR /app/apps/api
RUN chmod 0555 /app/apps/api/app/git_askpass.py
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH=/app/apps/api
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
