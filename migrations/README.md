# Database Migrations

This directory contains SQL migration scripts for the fraud detection database.

## Applying Migrations

### Option 1: Using psql (Recommended for production)

```bash
# Connect to PostgreSQL and run migration
psql -h localhost -U user -d bankdb -f migrations/001_add_indexes.sql
```

### Option 2: Using Docker

```bash
# If database is running in Docker
docker exec -i <postgres_container_name> psql -U user -d bankdb < migrations/001_add_indexes.sql
```

### Option 3: Using Python

```python
from sqlalchemy import create_engine, text
import os

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://user:password@localhost/bankdb")
engine = create_engine(DATABASE_URL)

with open('migrations/001_add_indexes.sql', 'r') as f:
    migration_sql = f.read()

with engine.connect() as conn:
    conn.execute(text(migration_sql))
    conn.commit()

print("Migration completed successfully")
```

## Migration History

| Migration | Description | Date | Status |
|-----------|-------------|------|--------|
| 001_add_indexes.sql | Add performance indexes | 2025-12-14 | Pending |

## Future Migrations

In production, consider using a proper migration tool like:
- **Alembic** (Python-based, recommended for SQLAlchemy projects)
- **Flyway** (Java-based, enterprise-grade)
- **Liquibase** (XML/YAML-based, database-agnostic)

### Setting up Alembic (Next Step)

```bash
pip install alembic
alembic init alembic
# Edit alembic.ini with database URL
# Create migrations: alembic revision --autogenerate -m "description"
# Apply migrations: alembic upgrade head
```
