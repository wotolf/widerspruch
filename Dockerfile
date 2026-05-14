FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ backend/
COPY alembic.ini .
COPY alembic/ alembic/
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh
RUN useradd --no-create-home --shell /bin/false botuser
USER botuser
ENTRYPOINT ["/app/entrypoint.sh"]