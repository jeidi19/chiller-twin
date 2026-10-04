# One image for the three Python services; docker-compose.yml picks the command.
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

COPY pyproject.toml README.md ./
COPY simulator/ simulator/
COPY gateway/ gateway/
COPY collector/ collector/
RUN pip install ".[opcua,mqtt,influx]"

COPY configs/ configs/

USER nobody
