# Assay Dashboard - Backend API

FastAPI backend for the Assay Dashboard application. Provides REST API endpoints for the mobile app and handles database operations, authentication, notifications, and sync services.

## Overview

This backend serves as the central API for:
- **Mobile App (React Native)**: User authentication, assay viewing, notifications
- **Sync Service**: Database synchronization between local office and cloud

## Tech Stack

- **Framework**: FastAPI (Python 3.10+)
- **Database**: MySQL 8.0
- **ORM**: SQLAlchemy 2.0
- **Authentication**: JWT (access + refresh tokens)
- **Password Hashing**: PBKDF2 with salt

## Project Structure

```
assayapp-backend/
├── main.py                 # FastAPI application entry point
├── config.py               # Configuration management (pydantic-settings)
├── database.py             # Database connection and session
├── models.py               # SQLAlchemy ORM models
├── schemas.py              # Pydantic schemas for validation
├── .env                    # Environment variables (not in git)
├── .env.example            # Environment template
├── requirements.txt        # Python dependencies
│
├── routers/                # API route handlers
│   ├── auth.py             # Authentication (login, logout, refresh)
│   ├── users.py            # User management
│   ├── assayresult.py      # Assay CRUD and search
│   ├── analytics.py        # Business analytics endpoints
│   ├── notifications.py    # Push notifications
│   ├── pdf.py              # PDF generation
│   └── sync.py             # Database sync endpoints
│
└── services/               # Business logic services
    └── pdf_generator.py    # PDF generation service
```

## Database Models

| Model | Description | Primary Use |
|-------|-------------|-------------|
| `User` | All users (customers + staff) | Authentication, customer data |
| `AssayResult` | Gold/metal assay test results | Core business data |
| `SpoilRecord` | Rejected/spoiled assay records | Quality tracking |
| `Loss` | Loss percentage lookup table | Calculations |
| `Notification` | Mobile push notifications | User alerts |
| `PushToken` | Expo push notification tokens | Mobile devices |
| `RefreshToken` | JWT refresh token storage | Auth sessions |

## User Roles

| Role | Permissions |
|------|-------------|
| `customer` | View own assays, notifications, change password |
| `worker` | All customer permissions + view all customers |
| `admin` | All permissions + analytics, reports, set passwords |
| `boss` | Same as admin |

## API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/login` | Login with phone/password |
| POST | `/auth/refresh` | Refresh access token |
| POST | `/auth/logout` | Logout and revoke tokens |
| POST | `/auth/change-password` | Admin sets user password |

### Assay Results
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/assay-results/` | List assays (paginated) |
| GET | `/assay-results/{id}` | Get single assay |
| GET | `/assay-results/search` | Search assays |
| PUT | `/assay-results/{id}/toggle-ready` | Toggle ready status |

### Users
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/users/` | List users |
| GET | `/users/{id}` | Get user details |
| POST | `/users/change-password` | Change own password |

### Analytics (Admin/Boss only)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/analytics/dashboard` | Dashboard metrics |
| GET | `/analytics/daily-report` | Daily report data |
| GET | `/analytics/trends` | Trend analysis |

### Notifications
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/notifications/` | List notifications |
| PUT | `/notifications/{id}/read` | Mark as read |
| PUT | `/notifications/read-all` | Mark all as read |
| DELETE | `/notifications/{id}` | Delete notification |
| POST | `/notifications/push-token` | Register push token |

### Sync (Internal use)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/sync/changes?since=` | Get changes since timestamp |
| POST | `/sync/push` | Push local changes to cloud |

## Installation

### Prerequisites
- Python 3.10+
- MySQL 8.0+
- pip

### Setup

```bash
# Clone or navigate to backend
cd assayapp-backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env

# Edit .env with your settings
# - DATABASE_URL
# - SECRET_KEY (generate new one for production)
# - SYNC_API_KEY
```

### Database Setup

```bash
# Create MySQL database
mysql -u root -p
CREATE DATABASE assay;
EXIT;

# Tables are created automatically on first run
```

### Run Development Server

```bash
# Start FastAPI with hot reload
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Or with specific settings
uvicorn main:app --reload --host $API_HOST --port $API_PORT
```

### Access API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

Note: Documentation is disabled in production mode.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ENVIRONMENT` | `development` or `production` | `development` |
| `DATABASE_URL` | MySQL connection string | Required |
| `SECRET_KEY` | JWT signing key | Required |
| `ALGORITHM` | JWT algorithm | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifetime | `30` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token lifetime | `120` |
| `SALT_SIZE` | Password salt size | `32` |
| `HASH_SIZE` | Password hash size | `32` |
| `ITERATIONS` | PBKDF2 iterations | `100000` |
| `CORS_ORIGINS` | Allowed origins (comma-separated) | `http://localhost:8081` |
| `API_HOST` | Server host | `0.0.0.0` |
| `API_PORT` | Server port | `8000` |
| `SYNC_API_KEY` | API key for sync service | Required |

## Production Deployment

### Environment Differences

| Feature | Development | Production |
|---------|-------------|------------|
| `/docs` endpoint | Enabled | Disabled |
| `/redoc` endpoint | Enabled | Disabled |
| Debug mode | On | Off |
| CORS | localhost | Your domain(s) |

### Production Checklist

- [ ] Set `ENVIRONMENT=production`
- [ ] Generate new `SECRET_KEY`: `python -c "import secrets; print(secrets.token_hex(32))"`
- [ ] Generate new `SYNC_API_KEY`: `python -c "import secrets; print(secrets.token_hex(32))"`
- [ ] Update `CORS_ORIGINS` with production domain(s)
- [ ] Use strong MySQL password
- [ ] Set up HTTPS (via reverse proxy)
- [ ] Configure firewall rules
- [ ] Set up database backups

### Docker Deployment

See the main project README for Docker Compose setup.

## Sync System

This backend includes endpoints for synchronizing with a local office database:

### How Sync Works

1. **Local Office** runs a separate sync service (see `assayapp-sync/`)
2. Sync service **polls** `/sync/changes` every 60 seconds
3. Changes are detected using `modified` timestamps
4. Local changes are **pushed** via `/sync/push`
5. Cloud changes are **pulled** and applied locally

### Sync Authentication

All sync endpoints require the `X-Sync-Key` header matching `SYNC_API_KEY`.

### What Gets Synced

| Direction | Data |
|-----------|------|
| Local → Cloud | Users, AssayResults, SpoilRecords, Losses |
| Cloud → Local | Password changes, Ready state changes |

### Notifications on Sync

When `assayresult.ready` changes to `true` during sync:
1. Notification record created
2. Push notification sent to customer's devices

## Health Check

```bash
# Check if API is running
curl http://localhost:8000/health

# Response
{
  "status": "healthy",
  "environment": "development"
}
```

## Development

### Code Style

- Follow PEP 8
- Use type hints
- Document functions with docstrings

### Adding New Endpoints

1. Create router in `routers/` directory
2. Define Pydantic schemas in `schemas.py`
3. Register router in `main.py`

### Database Migrations

Currently using SQLAlchemy's `create_all()` for table creation. For production with schema changes, consider using Alembic:

```bash
pip install alembic
alembic init migrations
# Configure and create migrations
```

## Troubleshooting

### Database Connection Issues

```bash
# Test MySQL connection
mysql -u root -p -h localhost assay

# Check if port is open
netstat -an | grep 3306
```

### CORS Errors

- Ensure `CORS_ORIGINS` includes your frontend URL
- Check for trailing slashes
- Verify protocol (http vs https)

### Token Issues

- Check `SECRET_KEY` matches between restarts
- Verify token expiration times
- Clear stored tokens and re-login

## License

Proprietary - Internal use only.
