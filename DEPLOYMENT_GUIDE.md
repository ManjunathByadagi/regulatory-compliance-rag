# Deployment Guide

## Prerequisites

- Ubuntu 22.04+
- Docker and docker-compose plugin
- 8 CPU, 32 GB RAM recommended for 10k+ docs

## Steps

1. Copy source package to server.
2. Create `.env` from `.env.example` and set API key, credentials, and paths.
3. Place PDFs under `data/raw` directories.
4. Build and run:

```bash
docker-compose up --build -d
```

5. Verify health:

```bash
curl http://localhost:8000/health
```

6. Ingest data:

```bash
curl -X POST "http://localhost:8000/ingest?root_dir=./data/raw" \
  -H "Authorization: Bearer <API_KEY>"
```

## Ops Notes

- Logs: `docker logs regulatory-rag-api`
- Restart: `docker-compose restart`
- Stop: `docker-compose down`
- Backup: persist `storage/` and `data/` volumes

## Scaling

- Front API replicas behind reverse proxy for 500+ concurrent users.
- Move SQLite to PostgreSQL for high-concurrency audit logging.
- Consider managed vector DB for large scale and HA.
