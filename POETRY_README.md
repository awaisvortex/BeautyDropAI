# 🎯 Poetry Setup - Quick Start

This project uses **Poetry** for dependency management with **Python 3.13.7**.

## 📦 Installation

### Step 1: Install Poetry

**Windows (PowerShell):**

```powershell
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | py -
```

**Linux/Mac:**

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

**Verify Installation:**

```bash
poetry --version
```

### Step 2: Automated Setup (Recommended)

**Windows:**

```bash
setup_poetry.bat
```

**Linux/Mac:**

```bash
chmod +x setup_poetry.sh
./setup_poetry.sh
```

This script will:

- ✅ Check Poetry installation
- ✅ Install all dependencies
- ✅ Create `.env` file
- ✅ Run database migrations
- ✅ Optionally create superuser
- ✅ Optionally seed sample data

### Step 3: Manual Setup (Alternative)

```bash
# 1. Install dependencies
poetry install

# 2. Activate virtual environment
poetry shell

# 3. Copy environment file
cp .env.example .env
# Then edit .env with your credentials

# 4. Run migrations
python manage.py makemigrations
python manage.py migrate

# 5. Create superuser (optional)
python manage.py createsuperuser

# 6. Seed data (optional)
python scripts/seed_data.py
python scripts/generate_slots.py

# 7. Run server
python manage.py runserver
```

## 🚀 Daily Usage

### Activate Environment

```bash
poetry shell
```

### Run Development Server

```bash
# Inside Poetry shell
python manage.py runserver

# Or without activating shell
poetry run python manage.py runserver
```

### Common Commands

```bash
# Run migrations
poetry run python manage.py migrate

# Create superuser
poetry run python manage.py createsuperuser

# Run tests
poetry run pytest

# Format code
poetry run black .
poetry run isort .

# Run linting
poetry run flake8
```

## 📋 Dependencies

### Production Dependencies

- Django 5.0.1
- Django REST Framework 3.14.0
- PostgreSQL (psycopg2-binary)
- Redis & django-redis
- Clerk Backend API
- Stripe
- Celery
- And more... (see `pyproject.toml`)

### Development Dependencies

- pytest & pytest-django
- black, isort, flake8
- mypy, pylint
- django-debug-toolbar
- ipython

## 🔧 Configuration Files

- **`pyproject.toml`** - Poetry configuration and dependencies
- **`poetry.toml`** - Poetry settings (creates `.venv` in project)
- **`poetry.lock`** - Locked dependency versions (auto-generated)

## 📚 Documentation

- **[POETRY_GUIDE.md](POETRY_GUIDE.md)** - Comprehensive Poetry guide
- **[SETUP.md](SETUP.md)** - Full setup instructions
- **[QUICKSTART.md](QUICKSTART.md)** - Quick reference

## 🆘 Troubleshooting

### Poetry not found

```bash
# Windows: Add to PATH
%APPDATA%\Python\Scripts

# Linux/Mac: Add to ~/.bashrc or ~/.zshrc
export PATH="$HOME/.local/bin:$PATH"
```

### Wrong Python version

```bash
# Use specific Python version
poetry env use python3.13
# Or full path
poetry env use C:\Python313\python.exe
```

### Dependency conflicts

```bash
# Clear cache and reinstall
poetry cache clear pypi --all
poetry install --no-cache
```

### Virtual environment issues

```bash
# Remove and recreate
poetry env remove python3.13
poetry install
```

## ✅ Verify Setup

After setup, verify everything works:

```bash
# Check Python version
poetry run python --version
# Should show: Python 3.13.7

# Check Django
poetry run python manage.py --version
# Should show: 5.0.1

# Check database connection
poetry run python manage.py check

# Run tests
poetry run pytest
```

## 🎉 You're Ready!

Your Django salon booking system is set up with Poetry!

**Start the server:**

```bash
poetry run python manage.py runserver
```

**Visit:**

- API: http://localhost:8000/api/v1/
- Docs: http://localhost:8000/api/docs/
- Admin: http://localhost:8000/admin/

---

**Need help?** Check [POETRY_GUIDE.md](POETRY_GUIDE.md) for detailed instructions.
