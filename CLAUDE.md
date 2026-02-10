# Brightness Assay Backend

## Architecture
- **Framework**: FastAPI (Python)
- **Database**: MySQL via SQLAlchemy (PyMySQL driver), pool size 12, max overflow 20
- **Auth**: JWT (python-jose) with access + refresh tokens, PBKDF2-HMAC-SHA256 password hashing
- **PDF**: ReportLab (A5 page size) for generating assay reports
- **Monitoring**: Sentry SDK
- **Deployment**: Local hosting via Cloudflare Tunnel (dashboard-managed)

## Push Notification Routing
- **iOS** → APNs directly (`services/apns.py`) with HTTP/2, collapse-id support
- **Android** → FCM V1 directly (`services/fcm.py`) with high priority
- **Fallback** → Expo Push API (for devices without native tokens)

## Key Files
| File | Purpose |
|------|---------|
| `main.py` | App entry point, CORS, router registration, health check |
| `models.py` | SQLAlchemy ORM models (9 models) |
| `schemas.py` | Pydantic request/response schemas |
| `database.py` | Database engine, session, connection pool config |
| `config.py` | Settings from .env (pydantic-settings) |
| `routers/auth.py` | Login, register, logout, token refresh, change password |
| `routers/users.py` | User CRUD, customer list, customer detail, autocomplete |
| `routers/assayresult.py` | Assay CRUD, search, mark-ready, batch-mark-ready |
| `routers/notifications.py` | Push routing, token registration, in-app notifications |
| `routers/analytics.py` | Dashboard metrics, date range, period analytics |
| `routers/pdf.py` | Single assay and formcode batch PDF generation |
| `routers/sync.py` | Local-cloud data synchronization |
| `routers/calculator.py` | Gold calculator recipe CRUD (all roles) |
| `routers/dependency.py` | Auth dependencies: get_current_user, get_admin_user, get_staff_user |
| `services/apns.py` | Direct APNs HTTP/2 push for iOS (alert + silent) |
| `services/fcm.py` | Direct FCM V1 push for Android |
| `services/pdf_generator.py` | ReportLab PDF layout and generation |
| `utils/password.py` | PBKDF2-HMAC-SHA256 hash/verify functions |
| `utils/date_helpers.py` | Period range calculation for analytics |
| `utils/assay_helpers.py` | build_assay_response() helper |
| `seed_test_data.py` | Create test accounts and assay data for App Store review |

## Database Models
| Model | Purpose |
|-------|---------|
| `User` | Customer/staff accounts with roles |
| `AssayResult` | Gold fire assay test results |
| `SpoilRecord` | Spoiled sample records |
| `Loss` | Loss percentage lookup table |
| `RefreshToken` | JWT refresh token storage |
| `Notification` | In-app notification records |
| `PushToken` | Device push tokens (Expo + native) |
| `MixRecipe` | Saved gold alloy calculator recipes (JSON alloy_mix) |

## Environment Variables (.env)
- `DATABASE_URL` — MySQL connection string
- `SECRET_KEY` — JWT signing key
- `ENVIRONMENT` — `development` or `production`
- `CORS_ORIGINS` — Comma-separated allowed origins
- `SYNC_API_KEY` — Sync endpoint authentication
- `FCM_PROJECT_ID` — Firebase project ID (default: `assayapp`)
- `FCM_SERVICE_ACCOUNT_PATH` — Path to Firebase service account JSON
- `APNS_KEY_ID`, `APNS_TEAM_ID`, `APNS_KEY_PATH` — APNs config
- `APNS_BUNDLE_ID` — iOS bundle ID (default: `com.brightnessassay.app`)
- `APNS_USE_SANDBOX` — `True` for dev/TestFlight, `False` for App Store

## User Roles
- `customer` / `testcustomer` — Basic customer access (own results only)
- `worker` / `testworker` — Staff access (all results, mark-ready); testworker can only manage testcustomer data
- `admin` / `boss` — Full access (analytics, reports, user management)

## Infrastructure (Work PC)
- **Work PC path**: `D:\Users\User\Documents\Assay\assayapp-backend`
- **API Domain**: `api.brightnessassay.com` → localhost:8000
- **Website Domain**: `brightnessassay.com` → localhost:3000
- **Tunnel**: `assay-api-managed` (dashboard-managed via Cloudflare Zero Trust)
- **Auto-start**: Windows Task Scheduler with VBS wrapper → `start-api.bat`
- **Logs**: `logs/api.log`
- Always use `127.0.0.1` instead of `0.0.0.0` to avoid firewall prompts on managed work PCs

## Key Patterns
- `services/fcm.py` must NOT import from `routers/notifications.py` (circular import)
- Push token registration happens on login from mobile app (`POST /notifications/push-token`)
- Mark-ready creates in-app notification + sends push to customer
- Mark-not-ready deletes old notifications, creates new one, sends visible push
- `google-auth` package required for FCM V1 OAuth2 authentication
- Production mode disables `/docs` and `/redoc` endpoints
- MySQL token columns use `String(500)` not `Text` (MySQL can't index TEXT without key length)
- Password hashing uses PBKDF2-HMAC-SHA256 with 100k iterations

## Troubleshooting
- **502 Bad Gateway**: FastAPI not running or MySQL not started
- **Intermittent 404s**: Stale Cloudflare Tunnel connectors — use dashboard-managed tunnel
- **Windows Defender blocks cloudflared**: Add exclusion for `C:\Program Files\Cloudflared\`
- **Push notifications not received on Android**: Bypass Expo, send via FCM directly
- **Push token not registering**: Frontend build must include `google-services.json`
- **BLOB/TEXT index error**: Use `String(500)` instead of `Text` for indexed columns

## App Store Review Test Accounts
- **Customer**: Phone `+60123456789`, Password `AppleReview123!`
- **Staff**: Phone `+60198765432`, Password `StaffReview123!`
- Seed script: `python seed_test_data.py`
