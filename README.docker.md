# MiniStack Console - Docker Deployment

Quick start guide for running MiniStack Console with Docker Compose.

## Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- 4GB RAM minimum
- 10GB disk space

## Quick Start

### 1. Start all services

```bash
docker-compose up -d
```

This starts:
- **MiniStack** (port 4566) - AWS emulator
- **FalkorDB** (port 6379) - Graph database
- **Control-Plane API** (port 3001) - REST API
- **MCP Server** (port 3100) - Model Context Protocol server
- **Web UI** (port 3000) - React frontend

### 2. Verify services are running

```bash
docker-compose ps
```

All services should show "Up" status.

### 3. Access the Web UI

Open your browser to:
```
http://localhost:3000
```

### 4. Test the API

```bash
curl http://localhost:3001/api/health
```

Expected response:
```json
{"status": "healthy"}
```

## Service Ports

| Service | Port | Description |
|---------|------|-------------|
| Web UI | 3000 | React frontend (nginx) |
| API | 3001 | Control-plane REST API |
| MCP Server | 3100 | Model Context Protocol server |
| MiniStack | 4566 | AWS service emulator |
| FalkorDB | 6379 | Graph database (Redis protocol) |

## Common Operations

### View logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api
docker-compose logs -f web
```

### Restart a service

```bash
docker-compose restart api
```

### Stop all services

```bash
docker-compose down
```

### Stop and remove volumes (⚠️ deletes all data)

```bash
docker-compose down --volumes
```

### Rebuild after code changes

```bash
# Rebuild specific service
docker-compose up -d --build api

# Rebuild all services
docker-compose up -d --build
```

## Data Persistence

Volumes are used to persist data across container restarts:

- `ministack_data` - MiniStack resource state
- `falkordb_data` - FalkorDB graph database

To inspect volumes:
```bash
docker volume ls | grep ministack_console
```

To backup FalkorDB data:
```bash
docker exec ministack_console_falkordb redis-cli --rdb /data/backup.rdb
```

## Development Workflow

### 1. Local development with hot reload

For API development:
```bash
# Stop the containerized API
docker-compose stop api

# Run API locally with hot reload
cd /path/to/ministack_console
python -m uvicorn api.main:app --reload --port 3001
```

For Web UI development:
```bash
# Stop the containerized web UI
docker-compose stop web

# Run UI locally with hot reload
cd web_ui
npm run dev
```

### 2. Rebuild after changes

```bash
docker-compose up -d --build
```

## Troubleshooting

### Service won't start

Check logs:
```bash
docker-compose logs <service-name>
```

### Port already in use

If a port is already in use, edit `docker-compose.yml` to change the host port:
```yaml
ports:
  - "3002:3001"  # Changed from 3001:3001
```

### Out of memory

Increase Docker's memory limit in Docker Desktop settings to at least 4GB.

### Reset everything

```bash
docker-compose down --volumes
docker-compose up -d
```

## Network Configuration

All services run on the `ministack_network` bridge network. Services can communicate using service names as hostnames:

- `http://ministack:4566` - MiniStack internal endpoint
- `http://falkordb:6379` - FalkorDB internal endpoint
- `http://api:3001` - API internal endpoint
- `http://mcp:3100` - MCP server internal endpoint

## Performance

Startup time: ~10 seconds (NFR-7)
- MiniStack: 2-3s
- FalkorDB: 1-2s
- API: 3-4s
- MCP: 2-3s
- Web UI: 1-2s

## Production Considerations

**⚠️ This configuration is for development only.**

For production:
1. Use proper secrets management (not environment variables)
2. Enable TLS/SSL for all services
3. Add authentication to MCP server (`MCP_REQUIRE_API_KEY=true`)
4. Use production-grade reverse proxy (Traefik, nginx)
5. Enable API rate limiting
6. Configure log aggregation
7. Set up monitoring and alerting
8. Use persistent volume mounts for data

## CI/CD Integration

### GitHub Actions example

```yaml
name: Test Docker Compose

on: [push]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Start services
        run: docker-compose up -d
      - name: Wait for services
        run: sleep 15
      - name: Health check
        run: |
          curl -f http://localhost:3001/api/health
          curl -f http://localhost:3000/health
      - name: Cleanup
        run: docker-compose down --volumes
```

## Support

For issues, see:
- [GitHub Issues](https://github.com/ministackorg/ministack-console/issues)
- [MiniStack Documentation](https://github.com/ministackorg/ministack)
