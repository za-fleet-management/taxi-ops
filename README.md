# TaxiOps — South African Taxi Fleet Management Platform

A comprehensive fleet management platform designed specifically for South African taxi operators. Built with FastAPI, SQLAlchemy, and SQLite for simplicity and reliability.

## Features

### Phase 0 (Foundation) ✅
- Multi-tenant architecture with row-level isolation
- JWT-based authentication (phone number login)
- Organisation and user management
- Secure data isolation between organisations
- RESTful API with FastAPI
- Database migrations with Alembic

### Phase 1 (In Progress)
- Complete authentication flows (signup/login/invite)
- Taxi and driver management
- Daily income and breakdown tracking
- Offline-first design with IndexedDB queue

### Phase 2 (Planned)
- Comprehensive reporting dashboard
- Income aggregation and analytics
- Driver performance metrics
- Downtime cost analysis

### Phase 3 (Planned)
- Fuel tracking and management
- Route assignment and tracking
- Route profitability analysis
- Cost-of-operations reporting

## Tech Stack

- **Backend**: Python 3.11+, FastAPI
- **Database**: SQLite with SQLAlchemy (sync)
- **Migrations**: Alembic
- **Authentication**: JWT with bcrypt (python-jose)
- **Templates**: Jinja2
- **Frontend**: htmx, Tailwind CSS (CDN), Vanilla JS
- **Testing**: pytest

## Installation

### Prerequisites

- Python 3.11 or higher
- pip (Python package manager)

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd taxi-ops
```

2. Create a virtual environment (recommended):
```bash
python -m venv venv

# On Windows
venv\Scripts\activate

# On Linux/Mac
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -e ".[dev]"
```

4. Create environment configuration:
```bash
# Create a .env file with the following variables
SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite:///./taxi_ops.db
```

5. Run database migrations:
```bash
alembic upgrade head
```

6. (Optional) Seed the database with test data:
```bash
python app/seed.py
python app/seed_admin.py
```

## Running the Application

### Development Server

```bash
uvicorn app.main:app --reload
```

The application will be available at `http://localhost:8000`

### Production Deployment

For production, use Gunicorn with Uvicorn workers:

```bash
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

## Development

### Creating Database Migrations

After modifying SQLAlchemy models:

```bash
alembic revision --autogenerate -m "description of changes"
alembic upgrade head
```

### Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_tenant_isolation.py -v

# Run with coverage
python -m pytest tests/ -v --cov=app
```

### Code Quality

The project follows these principles:

- **Multi-tenancy**: All queries filter by `organisation_id` from JWT claims
- **Currency**: Stored as integer cents (ZAR), displayed with `R` prefix
- **Phone-based auth**: Login uses phone numbers, not emails
- **UUID primary keys**: All models use UUID v4 TEXT primary keys
- **No external services**: Single SQLite file, no Redis/Postgres required

## Project Structure

```
taxi-ops/
├── alembic/                 # Database migrations
│   └── versions/            # Migration files
├── app/
│   ├── api/                 # API endpoints
│   │   ├── auth.py          # Authentication routes
│   │   ├── deps.py          # Dependencies (JWT verification)
│   │   ├── drivers.py       # Driver management
│   │   ├── taxis.py         # Taxi management
│   │   └── ...              # Other API modules
│   ├── core/
│   │   └── security.py      # JWT and bcrypt utilities
│   ├── models/              # SQLAlchemy ORM models
│   ├── schemas/             # Pydantic validation schemas
│   ├── services/            # Business logic services
│   ├── templates/           # Jinja2 HTML templates
│   ├── static/              # CSS and JS files
│   ├── config.py            # Configuration settings
│   ├── database.py          # Database session management
│   └── main.py              # FastAPI application
├── tests/                   # Test suite
├── .gitignore
├── alembic.ini              # Alembic configuration
├── pyproject.toml           # Project dependencies
├── AGENTS.md                # Agent instructions for development
└── README.md                # This file
```

## API Documentation

Once the server is running, interactive API documentation is available at:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Architecture

### Multi-Tenancy

TaxiOps implements row-level multi-tenancy:

- Each organisation has a unique `organisation_id`
- All tenant-scoped models include `organisation_id` foreign key
- JWT tokens contain `organisation_id` claim
- All queries automatically filter by `organisation_id`
- Tenant isolation is enforced at the database query level

### Authentication Flow

1. User logs in with phone number and password
2. Server validates credentials and returns JWT access token + refresh token (httpOnly cookie)
3. Access token TTL: 12 hours
4. Refresh token TTL: 30 days
5. All authenticated requests include `organisation_id` from token claims

### Offline Support

- IndexedDB stores pending operations when offline
- Background sync queue processes operations when connection restored
- Service worker caches static assets
- Progressive Web App (PWA) capabilities

## Security

- Passwords hashed with bcrypt (cost factor 12)
- JWT tokens with HS256 algorithm
- HttpOnly cookies for refresh tokens
- Row-level tenant isolation
- Input validation with Pydantic v2
- SQL injection prevention via SQLAlchemy ORM
- CORS configuration for production

## Testing Strategy

- **Unit tests**: Test individual functions and methods
- **Integration tests**: Test API endpoints with test database
- **Tenant isolation tests**: Verify no cross-tenant data leakage
- **Test database**: Separate SQLite file for testing

## Contributing

1. Read `AGENTS.md` for development guidelines
2. Follow the phase-based implementation order
3. Ensure all tests pass before submitting changes
4. Follow the Definition of Done checklist for each phase

## License

[Add your license information here]

## Support

[Add support contact information here]

## Changelog

### v0.1.0 - Phase 0 Complete
- Multi-tenant foundation
- JWT authentication
- Organisation and user models
- Database migrations
- Basic API structure
- Tenant isolation tests passing
