# Contributing to TaxiOps

Thank you for your interest in contributing to TaxiOps! This document provides guidelines and instructions for contributing.

## Development Philosophy

TaxiOps follows a **phase-based development approach**. Each phase must be completed fully before moving to the next. This ensures:

- Stable foundation before adding complexity
- Proper testing at each stage
- Clear progress tracking
- Reduced technical debt

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/your-username/taxi-ops.git
   cd taxi-ops
   ```
3. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
4. **Install dependencies**:
   ```bash
   pip install -e ".[dev]"
   ```
5. **Set up the database**:
   ```bash
   alembic upgrade head
   ```
6. **Run tests** to ensure everything works:
   ```bash
   python -m pytest tests/ -v
   ```

## Development Workflow

### 1. Create a Branch

Always work on a feature branch:

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b bugfix/issue-description
```

Branch naming conventions:
- `feature/` - New features
- `bugfix/` - Bug fixes
- `hotfix/` - Urgent production fixes
- `refactor/` - Code refactoring
- `docs/` - Documentation updates

### 2. Make Your Changes

Follow these guidelines:

#### Code Style
- Follow PEP 8 for Python code
- Use type hints where appropriate
- Keep functions focused and small
- Write self-documenting code with clear variable names

#### Documentation
- Update docstrings for new functions/classes
- Update README.md if adding new features
- Update AGENTS.md if changing development workflows

#### Testing
- Write tests for new features
- Ensure existing tests pass
- Aim for high test coverage
- Test multi-tenant isolation for any tenant-scoped code

### 3. Run Tests

Before committing:

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_tenant_isolation.py -v

# Check code coverage
python -m pytest tests/ --cov=app --cov-report=html
```

### 4. Database Migrations

If you modified models:

```bash
# Generate migration
alembic revision --autogenerate -m "descriptive message"

# Review the generated migration file in alembic/versions/

# Test the migration
alembic upgrade head

# Test rollback
alembic downgrade -1
alembic upgrade head
```

### 5. Commit Your Changes

Write clear, descriptive commit messages:

```bash
git add .
git commit -m "feat: add driver performance metrics

- Add aggregate query for driver income
- Create performance report endpoint
- Add tests for metric calculations"
```

Commit message format:
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `test:` - Adding/updating tests
- `refactor:` - Code refactoring
- `chore:` - Maintenance tasks

### 6. Push and Create Pull Request

```bash
git push origin feature/your-feature-name
```

Then create a Pull Request on GitHub with:
- Clear title describing the change
- Detailed description of what changed and why
- Reference any related issues
- Screenshots (if UI changes)
- Test results

## Code Review Process

1. Automated tests must pass
2. At least one maintainer approval required
3. No merge conflicts
4. Code follows project conventions
5. Documentation is updated

## Architecture Guidelines

### Multi-Tenancy Rules

**Critical**: Every tenant-scoped query MUST filter by `organisation_id`:

```python
# ✅ Correct
def get_taxis(db: Session, org_id: UUID):
    return db.query(Taxi).filter(Taxi.organisation_id == org_id).all()

# ❌ Wrong - Missing organisation_id filter
def get_taxis(db: Session):
    return db.query(Taxi).all()
```

The `organisation_id` comes from JWT token claims, never from request parameters.

### Currency Handling

Store money as **integer cents**, display with `R` prefix:

```python
# ✅ Correct
class Income(Base):
    total_cash = Column(Integer)  # Stored as cents
    
# Display
total_rand = total_cash / 100  # Convert to rands
display = f"R{total_rand:.2f}"

# ❌ Wrong - Using float for currency
total_cash = Column(Float)  # Will cause rounding errors
```

### Authentication

- Login uses **phone numbers**, not email
- JWT tokens are stateless
- Access token TTL: 12 hours
- Refresh token TTL: 30 days (httpOnly cookie)

### Database

- Use **UUID v4** for primary keys
- SQLite only (no PostgreSQL/MySQL in v1)
- Use Alembic for all schema changes
- Never modify database directly

### API Design

- FastAPI serves both HTML (Jinja2) and JSON (`/api/*`)
- Use Pydantic v2 for validation
- Return appropriate HTTP status codes
- Include proper error messages

## Testing Guidelines

### Test Structure

```python
def test_feature_name():
    """Test description of what is being tested."""
    # Arrange
    # ... setup test data
    
    # Act
    # ... perform the action
    
    # Assert
    # ... verify the results
```

### Multi-Tenant Tests

Always test tenant isolation:

```python
def test_tenant_isolation():
    """Ensure org A cannot access org B's data."""
    # Create data for org A
    # Try to access with org B credentials
    # Assert access is denied
```

See `tests/test_tenant_isolation.py` for examples.

## Phase-Based Development

### Current Phase Status

- ✅ **Phase 0**: Foundation complete
- 🚧 **Phase 1**: In progress
- ⏳ **Phase 2**: Planned
- ⏳ **Phase 3**: Planned

### Contributing to a Phase

1. Read `prompts/taxi-ops-build-python.md` for the phase specification
2. Check the Definition of Done for the phase
3. Ensure previous phases are complete
4. Don't skip ahead to future phases
5. Update phase status when complete

## Common Tasks

### Adding a New Model

1. Create model in `app/models/`
2. Add foreign key to `organisation_id` (for tenant-scoped models)
3. Create Pydantic schemas in `app/schemas/`
4. Generate migration: `alembic revision --autogenerate -m "add model_name"`
5. Write tests
6. Create API endpoints in `app/api/`

### Adding an API Endpoint

1. Create route in appropriate `app/api/` file
2. Use dependency injection for `get_current_user`
3. Validate input with Pydantic schemas
4. Filter by `organisation_id` from token
5. Write integration test
6. Update API documentation

### Fixing a Bug

1. Write a failing test that reproduces the bug
2. Fix the bug
3. Verify the test passes
4. Check for similar bugs elsewhere
5. Update documentation if needed

## Questions or Problems?

- Check existing issues on GitHub
- Read `AGENTS.md` for development guidelines
- Review `prompts/taxi-ops-build-python.md` for architecture details
- Create a new issue if needed

## Code of Conduct

- Be respectful and professional
- Welcome newcomers
- Provide constructive feedback
- Focus on the code, not the person
- Help others learn and grow

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.

---

Thank you for contributing to TaxiOps! 🚕
