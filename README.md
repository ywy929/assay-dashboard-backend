# Brightness Assay Backend

FastAPI backend for the Brightness Assay mobile application. Provides REST API endpoints for authentication, assay result management, push notifications, PDF generation, analytics, and local-cloud data synchronization.

## Tech Stack

- **Framework**: FastAPI (Python 3.10+)
- **Database**: MySQL 8.0 via SQLAlchemy 2.0 (PyMySQL driver), pool size 12, max overflow 20
- **Authentication**: JWT (python-jose) with access + refresh tokens
- **Password Hashing**: PBKDF2-HMAC-SHA256 with 100k iterations
- **PDF Generation**: ReportLab (A5 page size)
- **Push Notifications**: APNs (iOS), FCM V1 (Android), Expo (fallback)
- **Monitoring**: Sentry SDK
- **Deployment**: Local hosting via Cloudflare Tunnel (dashboard-managed)

## Project Structure

```
assayapp-backend/
├── main.py                     # FastAPI app entry point, CORS, router registration
├── config.py                   # Configuration from .env (pydantic-settings)
├── database.py                 # Database engine, session, connection pool config
├── models.py                   # SQLAlchemy ORM models
├── schemas.py                  # Pydantic request/response schemas
├── seed_test_data.py           # Create test accounts for App Store review
├── requirements.txt            # Python dependencies
├── .env                        # Environment variables (not in git)
│
├── routers/                    # API route handlers
│   ├── auth.py                 # Login, register, logout, token refresh
│   ├── users.py                # User CRUD, customer list, autocomplete
│   ├── assayresult.py          # Assay CRUD, search, mark-ready, batch-mark-ready
│   ├── analytics.py            # Dashboard metrics, trends, daily reports
│   ├── notifications.py        # Push routing, token registration, in-app notifications
│   ├── pdf.py                  # Single assay and formcode batch PDF generation
│   ├── sync.py                 # Local-cloud data synchronization
│   └── dependency.py           # Auth dependencies (get_current_user, get_admin_user, etc.)
│
├── services/                   # Business logic services
│   ├── apns.py                 # Direct APNs HTTP/2 push for iOS
│   ├── fcm.py                  # Direct FCM V1 push for Android
│   └── pdf_generator.py        # ReportLab PDF layout and generation
│
└── utils/                      # Utility modules
    ├── password.py             # PBKDF2-HMAC-SHA256 hash/verify
    ├── date_helpers.py         # Period range calculation for analytics
    └── assay_helpers.py        # build_assay_response() helper
```

## Database Models

| Model | Description |
|-------|-------------|
| `User` | Customer and staff accounts with roles |
| `AssayResult` | Gold fire assay test results |
| `SpoilRecord` | Spoiled sample records |
| `Loss` | Loss percentage lookup table |
| `RefreshToken` | JWT refresh token storage |
| `Notification` | In-app notification records |
| `PushToken` | Device push tokens (Expo + native APNs/FCM) |

## User Roles

| Role | Permissions |
|------|-------------|
| `customer` | View own assays, notifications, change password |
| `testcustomer` | Same as customer (used for App Store review) |
| `worker` | All customer permissions + view all customers, mark assays ready |
| `testworker` | Same as worker but restricted to testcustomer data only |
| `admin` / `boss` | Full access: analytics, reports, user management |

## API Endpoints

### Authentication (`/auth`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/register` | Create new user account |
| POST | `/login` | Authenticate with phone/password, return JWT tokens |
| POST | `/logout` | Revoke refresh token |
| POST | `/refresh` | Exchange refresh token for new tokens |
| POST | `/change-password` | Change password by user name |

### Users (`/users`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/all` | List all users (Admin only) |
| GET | `/me` | Get current user profile |
| GET | `/names` | User names for autocomplete (role-filtered) |
| GET | `/customers/names` | Customer names for autocomplete (Staff only) |
| GET | `/customers` | Paginated customer list with search |
| GET | `/customers/{customer_id}` | Customer detail |
| POST | `/change-password` | Change password for any user (Staff only) |
| GET | `/{user_id}` | Get user by ID (Admin only) |

### Assay Results (`/assay-results`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/my-results` | Paginated assay results (role-filtered) |
| GET | `/my-results/{result_id}` | Single assay result |
| GET | `/search` | Search with filters (itemcode, customer, date, fineness) |
| GET | `/all` | All assay results (Admin only) |
| GET | `/user/{user_id}` | Results for specific user (Admin only) |
| PUT | `/batch-mark-ready` | Batch set ready status |
| PUT | `/{assay_id}/mark-ready` | Toggle ready status and notify customer |

### Analytics (`/analytics`) — Staff/Admin only
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/date-range` | Oldest and newest assay dates |
| GET | `/dashboard` | Dashboard metrics for a period |
| GET | `/efficiency` | Processing time, weights, loss metrics |
| GET | `/trend` | Trend data (daily/monthly breakdown) |
| GET | `/customers/top` | Top customers by assay count |
| GET | `/trends/daily` | Daily trends for N days |
| GET | `/trends/monthly` | Monthly trends for N months |
| GET | `/daily-report` | Daily billing/coupon report by area (Admin/Boss only) |

### Notifications (`/notifications`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/push-token` | Register/update push notification token |
| DELETE | `/push-token/{token}` | Unregister push token |
| GET | `/` | List notifications (paginated, optionally unread only) |
| GET | `/stats` | Notification stats (total and unread count) |
| PUT | `/{notification_id}/read` | Mark notification as read |
| PUT | `/read-all` | Mark all as read |
| DELETE | `/{notification_id}` | Delete notification |

### PDF (`/pdf`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/generate/single/{assay_id}` | PDF for a single assay |
| GET | `/generate/{formcode}` | PDF for a formcode batch |

### Sync (`/sync`) — API key required
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/changes` | Records modified since timestamp |
| POST | `/push` | Push local changes to cloud |

## Push Notification Routing

Push notifications are routed based on the device's native token availability:

| Platform | Route | Service |
|----------|-------|---------|
| iOS | APNs directly via HTTP/2 | `services/apns.py` |
| Android | FCM V1 directly | `services/fcm.py` |
| Fallback | Expo Push API | For devices without native tokens |

- Token registration happens on login from the mobile app (`POST /notifications/push-token`)
- Mark-ready creates an in-app notification and sends a push to the customer
- Mark-not-ready deletes old notifications, creates a new one, and sends a visible push

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | MySQL connection string | Required |
| `SECRET_KEY` | JWT signing key | Required |
| `ENVIRONMENT` | `development` or `production` | `development` |
| `CORS_ORIGINS` | Allowed origins (comma-separated) | `http://localhost:8081` |
| `SYNC_API_KEY` | API key for sync service | Required |
| `FCM_PROJECT_ID` | Firebase project ID | `assayapp` |
| `FCM_SERVICE_ACCOUNT_PATH` | Path to Firebase service account JSON | — |
| `APNS_KEY_ID` | APNs authentication key ID | — |
| `APNS_TEAM_ID` | Apple Developer team ID | — |
| `APNS_KEY_PATH` | Path to APNs `.p8` key file | — |
| `APNS_BUNDLE_ID` | iOS bundle ID | `com.brightnessassay.app` |
| `APNS_USE_SANDBOX` | `True` for dev/TestFlight, `False` for production | `True` |

## Installation

### Prerequisites
- Python 3.10+
- MySQL 8.0+

### Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your database URL, secret key, etc.
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
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

API docs available at http://localhost:8000/docs (disabled in production).

## Sync System

Synchronizes data between the local office database and the cloud:

1. Local sync service polls `/sync/changes` periodically
2. Changes are detected using `modified` timestamps
3. Local changes are pushed via `/sync/push`
4. Requires `X-Sync-Key` header matching `SYNC_API_KEY`

| Direction | Data |
|-----------|------|
| Local -> Cloud | Users, AssayResults, SpoilRecords, Losses |
| Cloud -> Local | Password changes, ready state changes |

When an assay is marked ready during sync, a notification is created and pushed to the customer.

## Production Deployment

The backend runs on a local Windows machine exposed via Cloudflare Tunnel:

- **API**: `api.brightnessassay.com` -> localhost:8000
- **Tunnel**: Dashboard-managed via Cloudflare Zero Trust
- **Auto-start**: Windows Task Scheduler with VBS wrapper -> `start-api.bat`
- **Logs**: `logs/api.log`

### Production Checklist

- [ ] Set `ENVIRONMENT=production`
- [ ] Generate `SECRET_KEY`: `python -c "import secrets; print(secrets.token_hex(32))"`
- [ ] Generate `SYNC_API_KEY`: `python -c "import secrets; print(secrets.token_hex(32))"`
- [ ] Update `CORS_ORIGINS` with production domain(s)
- [ ] Configure FCM service account JSON for Android push
- [ ] Configure APNs key (`.p8` file) for iOS push, set `APNS_USE_SANDBOX=False`
- [ ] Use strong MySQL password
- [ ] Set up database backups

## App Store Review

Test accounts are created via the seed script:

```bash
python seed_test_data.py
```

- **Customer**: Phone `+60123456789`, Password `AppleReview123!`
- **Staff**: Phone `+60198765432`, Password `StaffReview123!`

## Health Check

```bash
curl http://localhost:8000/health
# {"status": "healthy", "environment": "development"}
```

## Troubleshooting

- **502 Bad Gateway**: FastAPI not running or MySQL not started
- **Intermittent 404s**: Stale Cloudflare Tunnel connectors — use dashboard-managed tunnel
- **CORS errors**: Ensure `CORS_ORIGINS` includes your frontend URL (no trailing slash)
- **Push not received (Android)**: Ensure FCM service account is configured and `google-services.json` is in the frontend build
- **Push not received (iOS)**: Check APNs key config and sandbox setting
- **Token issues**: Verify `SECRET_KEY` matches between restarts; clear tokens and re-login

## License

Proprietary — Internal use only.
