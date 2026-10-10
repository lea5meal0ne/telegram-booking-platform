# Telegram Booking Platform

[![CI](https://github.com/lea5meal0ne/telegram-booking-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/lea5meal0ne/telegram-booking-platform/actions/workflows/ci.yml)

A configurable appointment platform for one business per deployment, combining a Telegram bot, a mobile React Mini App, and a PostgreSQL-backed API. Services, prices, business content, working hours, booking rules, and portfolio content are managed through the administrator interface. No industry-specific services or customer records are preloaded.

Russian is the default interface language. Customers and administrators can switch to English; preferences are shared between the bot and Mini App.

## Features

- **Customer booking:** service selection, monthly availability calendar, live time slots, confirmation summary, appointment history, customer confirmation, cancellation, and rescheduling.
- **Availability:** weekly time windows, date overrides, breaks, blocked intervals, holidays and vacation ranges, timezone handling, notice period, booking horizon, slot interval, and cleanup buffer.
- **Administration:** dashboard, day/week/month schedule views, searchable appointment list and history, attendance verification, service editor, bilingual business settings, portfolio/category management, support inbox, and review moderation.
- **Telegram bot:** `/start`, `/help`, `/book`, `/appointments`, `/support`, `/cancel`, `/admin`, and `/language`; Mini App links, appointment callbacks, private support messages and photos, and administrator replies.
- **Persistent notifications:** customer and administrator booking messages, reminders, independent confirmation flags, post-appointment attendance requests, review invitations, retries, and restart recovery.
- **Verified reviews:** only the appointment owner can review an administrator-verified visit, once per appointment. No-show and canceled appointments are ineligible. Moderators can hide reviews but cannot change their ratings.
- **Portfolio:** categories, localized descriptions, ordering, multiple uploaded images, category filtering, and a fullscreen viewer.
- **Private support:** conversation history, photo attachments, Mini App and bot replies, close/reopen actions, and backend ownership checks.
- **Security:** Telegram HMAC validation, timestamp validation, one-time launch exchange, expiring opaque Redis sessions, server-side administrator allowlist, rate limiting, image decoding/re-encoding, private support media, and environment-based secrets.
- **Operations:** Docker Compose, automatic migrations, PostgreSQL and upload persistence, Redis persistence, Caddy HTTPS, health checks, non-root Python containers, automated tests, and GitHub Actions.

## Interface previews

These screenshots were captured from real browser tests with synthetic records saved through the API.

<img src="docs/screenshots/booking.png" width="280" alt="Russian customer booking summary" /> <img src="docs/screenshots/admin.png" width="280" alt="English administrator business settings" />

## Technology and architecture

Python 3.12+, FastAPI, aiogram 3, async SQLAlchemy 2, PostgreSQL 17, Alembic, Redis 7, and a persistent database job worker. React 19, TypeScript, Vite, Tailwind CSS, TanStack Query, React Router, react-i18next, Telegram Mini Apps SDK, and Lucide power the Mini App.

```mermaid
flowchart LR
  Customer[Telegram customer] --> Bot[aiogram bot]
  Customer --> Mini[React Mini App]
  Admin[Telegram administrator] --> Mini
  Mini --> Proxy[Caddy HTTPS]
  Proxy --> Web[Nginx static build]
  Proxy --> API[FastAPI]
  API --> DB[(PostgreSQL)]
  Bot --> DB
  Worker[Notification worker] --> DB
  Worker --> Telegram[Telegram Bot API]
  API --> Redis[(Redis sessions and rate limits)]
  Bot --> Redis
```

The API, bot, and worker share domain services and database models. PostgreSQL stores users, settings, services, schedule rules, appointments, status history, reviews, portfolio categories/items, support conversations/messages, and notification jobs. Confirmation and attendance records are stored with their appointment; review eligibility is derived from verified attendance. Localized content and image collections use JSON columns. Future employee or tenant support will require adding resource ownership to the locking and overlap constraints; this release has one shared appointment resource.

Bookings hold a PostgreSQL transaction advisory lock, recheck availability, and write the appointment and notification jobs atomically. A PostgreSQL `tstzrange` exclusion constraint independently prevents overlapping active bookings, including their cleanup buffer. Appointment snapshots preserve the original service name, price, currency, and duration through later edits and rescheduling.

See [architecture and lifecycle details](docs/ARCHITECTURE.md).

## Repository structure

```text
backend/
  app/                 API, bot, authentication, schemas, repositories, domain services, worker
  migrations/          Immutable Alembic PostgreSQL migrations
  tests/               Real PostgreSQL/Redis integration tests and bot tests
  requirements.lock    Pinned production Python dependencies
frontend/
  src/                 Customer/admin interfaces, API client, shared UI, translations
  e2e/                 Real-browser booking and administrator workflows
infra/
  Caddyfile            HTTPS and reverse proxy configuration
  compose.test.yml     Isolated local development/test services
scripts/               Translation parity and secret scanning
.github/workflows/     Backend, frontend, browser, and Docker CI
```

## Local development

Prerequisites: Python 3.12+, Node.js 22.12+ (or a newer compatible LTS), and Docker with Compose.

```bash
git clone https://github.com/lea5meal0ne/telegram-booking-platform.git
cd telegram-booking-platform
python3 -m venv .venv
.venv/bin/pip install -c backend/requirements-test.lock -e './backend[test]'
docker compose -f infra/compose.test.yml up -d --wait
```

Apply migrations to the isolated development database:

```bash
cd backend
DATABASE_URL=postgresql+asyncpg://postgres:test-only-password@127.0.0.1:55432/postgres ../.venv/bin/alembic upgrade head
cd ..
```

Start the API from the repository root:

```bash
ENVIRONMENT=development DEV_AUTH=true ADMIN_IDS=900 \
DATABASE_URL=postgresql+asyncpg://postgres:test-only-password@127.0.0.1:55432/postgres \
REDIS_URL=redis://127.0.0.1:56379/14 \
.venv/bin/uvicorn app.api:app --app-dir backend --reload --port 8000 --no-access-log
```

In another terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open `http://localhost:5173/?dev_user=900` and use the development login button for administrator access. Any other local user ID is a customer. Add services and working hours before testing bookings. Development login exists only in Vite's development build and requires both `ENVIRONMENT=development` and `DEV_AUTH=true` on the API. Production configuration rejects development authentication.

API documentation: `http://localhost:8000/api/docs`. The Vite proxy forwards `/api` to the local API. The development account system is completely separate from Telegram authentication.

## Production environment

```bash
cp .env.example .env
chmod 600 .env
```

Edit `.env` locally; never commit it. Required production configuration:

| Variable | Purpose |
| --- | --- |
| `BOT_TOKEN` | Token issued by BotFather; backend/bot/worker only |
| `ADMIN_IDS` | Comma-separated trusted numeric Telegram user IDs |
| `DOMAIN` | Public DNS name pointing to your VPS |
| `MINI_APP_URL` | `https://` URL for the same public domain |
| `POSTGRES_USER`, `POSTGRES_DB` | Database identity |
| `POSTGRES_PASSWORD` | Strong generated database password |
| `DATABASE_URL` | Async PostgreSQL URL matching the database credentials |
| `REDIS_URL` | Internal Redis URL, usually `redis://redis:6379/0` |
| `UPLOADS_DIR` | Persistent upload directory, `/data/uploads` in Compose |
| `ENVIRONMENT` | `production` |
| `DEV_AUTH` | `false` |

URL-encode special characters in the password used inside `DATABASE_URL`. The settings model also accepts `AUTH_MAX_AGE` (default 3600 seconds). Business timezone and booking policies are edited in the admin Mini App and saved in PostgreSQL.

## VPS deployment and HTTPS

Use a Linux VPS with Docker Engine and Compose. A small deployment can start with 2 GB RAM and one or two CPUs; measure actual resource use and database growth. Configure DNS for `DOMAIN`, open ports 80/443, and install the repository on the server.

```bash
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 api bot worker
docker compose exec api python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/api/health').read().decode())"
```

Caddy obtains and renews certificates automatically once DNS and public ports are working. Only Caddy publishes ports; PostgreSQL, Redis, API, and Nginx remain on the private Compose network. The migration container must complete successfully before API startup. Database, uploads, Redis, and TLS state have named volumes.

Verify `https://YOUR_DOMAIN/api/health` and open the Mini App from Telegram. The bot uses long polling; run one bot instance per token. The worker retries failures with exponential backoff, up to ten attempts; failed jobs can be inspected and retried in the admin dashboard. Run one worker initially.

### BotFather setup

1. Create a bot with `/newbot` in the official `@BotFather` account.
2. Store its token in `.env` as `BOT_TOKEN`.
3. Set the bot's menu button using `/setmenubutton` to your public `MINI_APP_URL`.
4. Configure the main Mini App using BotFather's Mini App settings, with the same HTTPS URL. Configure the allowed domain where BotFather requests it.
5. Add trusted numeric Telegram user IDs to `ADMIN_IDS` and restart API, bot, and worker after allowlist changes.
6. Every administrator must send `/start` to the bot so Telegram permits direct notifications. Customers also need to start the bot to receive reminders.
7. Open `/admin`, configure business information, create services, and add working hours. Check the resulting availability as a customer.

Command descriptions are registered in Russian and English when the bot starts. Tokens never appear in browser code or image URLs.

### Updates, migrations, and backups

```bash
git pull --ff-only
docker compose build
docker compose run --rm migrate
docker compose up -d --force-recreate api bot worker web
```

Back up before applying migrations. The initial migration enables `btree_gist`; the database role must be allowed to create that extension. When adding schema changes, create a new immutable migration rather than editing an applied revision.

```bash
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > booking-backup.sql
```

Back up the `uploads` volume alongside the database. Store backups off the VPS, restrict access, and test restores. Plan retention, deletion requests, database maintenance, and notification-failure monitoring with the business operator. A data deletion request is registered and sent to administrators; deletion is a manual retention-aware process, not an automatic purge of appointment history.

## Testing and quality checks

The backend tests truncate their database tables. Use only the isolated test services, never a production database.

```bash
docker compose -f infra/compose.test.yml up -d --wait
cd backend
DATABASE_URL=postgresql+asyncpg://postgres:test-only-password@127.0.0.1:55432/postgres ../.venv/bin/alembic upgrade head
../.venv/bin/pytest -q
../.venv/bin/ruff check .
../.venv/bin/ruff format --check .
cd ../frontend
npm ci
npm test
npm run lint
npm run build
npm audit --audit-level=moderate
cd ..
python3 scripts/scan-secrets.py
```

Browser tests use real HTTP endpoints and persisted test records, rather than mocked availability. Run them after the backend tests, or give them a separate database through `DATABASE_URL`. Their API automatically starts with development authentication.

```bash
cd frontend
npx playwright install chromium
npm run test:e2e
```

CI runs backend tests on PostgreSQL/Redis, frontend component tests, translation parity, type checks, production builds, browser workflows, a secret scan, and both Docker builds. CI does not automatically deploy or send real Telegram messages.

The local verification record is maintained in [docs/VERIFICATION.md](docs/VERIFICATION.md). Live bot delivery and public HTTPS deployment require operator credentials and are separate from automated test verification.

## Localization

- `backend/app/i18n.py` contains centralized bot, notification, and error messages.
- `frontend/src/locales/ru.json` and `en.json` contain all Mini App translations.
- Initial language detection uses Russian for missing Telegram language metadata or `ru*`, and English for other Telegram language codes.
- PostgreSQL `users.language` is authoritative. Explicit selections persist across launches/devices; bot notifications resolve the preference when they are sent.
- Missing English business content falls back to Russian. Reviews and private support text are shown exactly as their authors wrote them.
- Money uses integer minor units; browser formatting uses the selected language and currency. Appointment times use the configured business timezone.

To add a UI message, add matching translation keys and interpolation placeholders in both JSON files and call `t(key)`. For bot messages, add a translation pair and call `tr(key, user.language)`. To add another language, extend the backend language validator, translations, detection policy, frontend i18next resources, and both selectors. Run the localization checks and form-state tests.

## Security and operational limits

Telegram initialization data is HMAC-verified with the bot token, checked for freshness, and exchanged once for an opaque 24-hour session. Redis stores sessions, launch digests, and request quotas. The browser stores the session in session storage; reopening Telegram generates a new signed launch. Authorization is enforced in the API and domain services, including bot callbacks. API access logs are disabled to avoid logging sensitive launch data.

Uploaded images are limited to 8 MB and 20 megapixels, decoded with Pillow, resized, and re-encoded as JPEG without source metadata. Unpublished uploads are not publicly accessible. Support attachments require a bearer token and conversation ownership. Public service and portfolio images are intentionally public. HTTPS and the reverse proxy's content security policy protect the web interface.

The notification worker provides persistent, retryable **at-least-once** delivery. PostgreSQL row locks and serialized booking mutations prevent normal duplicate processing, but Telegram has no send-message idempotency key: a process crash after Telegram accepts a message and before the database commits may produce one duplicate notification. Business actions and review submissions remain protected by authorization and database constraints.

This release supports a single shared booking resource. It does not implement payment processing, tenant separation, employee assignment, or automatic data erasure. Public live deployment and real Telegram delivery have not been verified without the operator's token, domain, and VPS access.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| No available dates | Add active services and working hours; check date blocks, duration/buffer, notice period, horizon, and timezone |
| Telegram login rejected | Launch inside Telegram, check token and clock, and reopen for fresh initialization data |
| Admin menu absent | Use your numeric Telegram ID in `ADMIN_IDS`, then restart processes |
| No Telegram notification | Start the bot as that account; inspect worker logs and failed jobs |
| Migration fails | Check database URL/password and permission to create `btree_gist` |
| HTTPS unavailable | Check domain DNS, inbound ports, Caddy logs, and certificate state |
| Support photo unavailable | Use the authenticated Mini App; support attachments are not public URLs |
| Development login rejected | Use a Vite dev build and set both development flags explicitly |
| Browser test schedule conflict | Use a fresh isolated database; existing bookings intentionally block incompatible schedule changes |

## Future improvements

Resource-aware employee scheduling and multiple businesses, optional payments, object-storage uploads, stronger operational dashboards, customer self-service export/retention workflows, and expanded accessibility/browser-device coverage can be added without replacing the shared API/domain architecture.

## License

[MIT](LICENSE).
