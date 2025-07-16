# Globant Data Engineering Challenge - FastAPI Solution

A production-ready REST API for CSV data ingestion and analytics, built with FastAPI, PostgreSQL, and Celery.

## 🚀 Features

- **Asynchronous CSV Processing**: Upload large CSV files processed by Celery workers using PostgreSQL COPY for optimal performance
- **Batch API**: Insert 1-1000 rows per request with validation
- **Analytics Endpoints**: Pre-computed materialized views for fast queries
- **Database Partitioning**: Automatic yearly partitions using pg_partman
- **Observability**: Prometheus metrics, Grafana dashboards, and distributed tracing
- **Container-Native**: Multi-stage Docker builds, Docker Compose orchestration
- **Production-Ready**: Health checks, graceful shutdowns, connection pooling

## 📋 Requirements

- Docker & Docker Compose
- Python 3.11+ (for local development)
- 4GB RAM minimum
- 10GB disk space

## 🏃‍♂️ Quick Start

1. Clone the repository:
```bash
git clone <repository-url>
cd globant-challenge
```

2. Copy environment variables:
```bash
cp .env.example .env
```

3. Start all services:
```bash
docker-compose up -d
```

4. Check service health:
```bash
curl http://localhost:8000/api/v1/health
```

5. Access services:
- API Documentation: http://localhost:8000/docs
- Celery Flower: http://localhost:5555
- Grafana: http://localhost:3000 (admin/admin)
- Prometheus: http://localhost:9090

## 🛠️ Makefile Commands

Run `make help` to list all available targets.

| Target | Description |
| ------ | ----------- |
| `make build` | Build all Docker images |
| `make up` | Start all services |
| `make down` | Stop all services |
| `make restart` | Restart all services |
| `make logs` | Show logs from all services |
| `make logs-api` | Show API logs |
| `make logs-worker` | Show worker logs |
| `make test` | Run tests inside Docker containers |
| `make test-local` | Run tests locally on the host machine |
| `make shell-api` | Open an interactive shell inside the API container |
| `make shell-db` | Open a PostgreSQL shell inside the DB container |
| `make clean` | Remove containers, volumes, and temporary files |
| `make upload-departments` | Upload sample `departments.csv` |
| `make upload-jobs` | Upload sample `jobs.csv` |
| `make upload-employees` | Upload sample `hired_employees.csv` |
| `make upload-all` | Upload all sample CSV files |
| `make analytics-quarterly` | Fetch quarterly hires analytics |
| `make analytics-departments` | Fetch departments above-average analytics |

## 📚 API Endpoints

### CSV Upload
```bash
# Upload departments CSV
curl -X POST "http://localhost:8000/api/v1/upload/csv/departments" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@departments.csv"

# Check task status
curl "http://localhost:8000/api/v1/task/{task_id}"
```

### Batch Insert
```bash
# Insert departments
curl -X POST "http://localhost:8000/api/v1/batch/departments" \
  -H "Content-Type: application/json" \
  -d '{
    "table": "departments",
    "rows": [
      {"id": 1, "department": "Engineering"},
      {"id": 2, "department": "Sales"}
    ]
  }'
```

### Analytics

#### Quarterly Hires
```bash
curl "http://localhost:8000/api/v1/analytics/hired/by-quarter?year=2021"
```

#### Departments Above Average
```bash
# JSON format
curl "http://localhost:8000/api/v1/analytics/departments/above-average?year=2021"

# CSV format
curl "http://localhost:8000/api/v1/analytics/departments/above-average?year=2021&format=csv"
```

## 🏗️ Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   FastAPI   │────▶│    Redis     │────▶│   Celery    │
│   (API)     │     │   (Queue)    │     │  (Workers)  │
└─────────────┘     └──────────────┘     └─────────────┘
       │                                         │
       ▼                                         ▼
┌─────────────┐                          ┌─────────────┐
│ PostgreSQL  │◀─────────────────────────│   COPY      │
│(Partitioned)│                          │  Command    │
└─────────────┘                          └─────────────┘
```

### Database Schema

- **departments**: id, department
- **jobs**: id, job  
- **hired_employees**: id, name, hire_dt, department_id, job_id
  - Partitioned by year using pg_partman
  - Indexed on (department_id, job_id, hire_dt)

### Materialized Views

- **mv_hires_q**: Quarterly aggregation for analytics
- **mv_dept_mean**: Departments above yearly average
- Auto-refreshed every 5 minutes via pg_cron

## 🧪 Testing

Run tests with Docker:
```bash
docker-compose run --rm api pytest -v
```

Run tests locally:
```bash
python -m pytest tests/ -v
```

Test coverage:
```bash
python -m pytest --cov=app tests/
```

## 📊 Performance

- **CSV Processing**: 50-80k rows/second on t3.medium
- **API Latency**: <40ms p95 for analytics queries
- **Batch Insert**: 1000 rows in <200ms
- **Concurrent Users**: Tested up to 1000 with Locust

## 🔧 Configuration

Key environment variables:

```env
# Database
DATABASE_URL=postgresql://user:pass@host:5432/db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres

# Performance
BATCH_SIZE=50000
CHUNK_SIZE=8388608  # 8MB
MAX_UPLOAD_SIZE=2147483648  # 2GB

# Workers
CELERY_WORKERS=2
```

## 📈 Monitoring

### Metrics
- Request latency (p50, p95, p99)
- CSV processing throughput
- Queue depth and worker utilization
- Database connections and query time

### Dashboards
1. Import Grafana dashboards from `docker/grafana/dashboards/`
2. Available dashboards:
   - API Performance
   - Celery Workers
   - PostgreSQL Statistics

## 🚀 Production Deployment

### Scaling
```bash
# Scale workers
docker-compose up -d --scale worker=4

# Scale API
docker-compose up -d --scale api=3
```

### Database Maintenance
```sql
-- Refresh materialized views manually
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_hires_q;

-- Add new partition
SELECT partman.create_parent('public.hired_employees', 'hire_year', 'native', 'yearly');
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Run tests: `pytest`
4. Submit a pull request

## 📝 License

This project is licensed under the MIT License. 