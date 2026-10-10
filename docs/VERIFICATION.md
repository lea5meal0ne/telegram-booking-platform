# Verification record

Executed locally on October 10, 2026. PostgreSQL 17 and Redis 7 ran in isolated Docker containers. Test customer and administrator records were synthetic and persisted through the actual backend.

| Check | Executed result |
| --- | --- |
| Backend and bot suite, host Python 3.14 | 39 passed |
| Backend and bot suite, production Python 3.12 image | 39 passed |
| React component tests | 4 passed |
| Chromium mobile end-to-end workflows | 2 passed |
| TypeScript validation | Passed |
| Russian/English frontend translation parity | 150 matching keys and placeholders |
| Bot translation placeholders and fallback | Passed in backend suite |
| Ruff lint and formatting | Passed |
| Vite production build | Passed |
| npm dependency audit | 0 vulnerabilities |
| Backend Docker image | Built successfully |
| Frontend/Nginx Docker image | Built successfully |
| Built API HTTP health | `{"status":"ok"}` with real PostgreSQL/Redis |
| Built frontend SPA routes | `/book` and `/appointments` returned production HTML |
| Production Docker Compose configuration | Validated with example environment and without loading secrets |
| Caddy HTTPS configuration | `Valid configuration` from `caddy validate` |
| Initial migration on a fresh PostgreSQL database | Applied successfully with overlap exclusion constraint |
| Secret scan | Passed; environment secrets and generated build/test directories are ignored |

The backend suite covers signed initialization data and invalid authentication, replay rejection, administrator access, real database concurrency and exclusion constraints, booking idempotency, availability, cancellation, rescheduling with historical snapshots, independent confirmations, attendance and no-show handling, verified and duplicate reviews, reminder creation/retry/recovery, localized messages, bot menus and support routing, service/settings/portfolio APIs, media privacy, invalid inputs, support history pagination, and rate-limit bypass rejection.

The customer browser workflow uses real API calls to configure a service and schedule, book through the calendar, switch language while preserving the selected time, confirm an appointment, submit support text, and cancel. The administrator browser workflow creates a bilingual service and persists business settings across a page reload. Browser tests do not intercept API responses or supply mocked availability.

Screenshots in `docs/screenshots` come from these browser workflows and were visually inspected. They show synthetic test content rather than a live business.

## External checks still requiring operator configuration

Real Telegram message delivery, BotFather configuration, a public HTTPS domain, and VPS operation were not exercised. The user requested completion without those credentials. Bot handlers and notification rendering/delivery calls were tested with Telegram method doubles; database persistence, API authorization, and browser workflows were tested against actual running services. Caddy validation checks configuration syntax, not a public certificate issuance.

GitHub Actions is configured to repeat backend, frontend, browser, and Docker checks. Its published run results are available in the repository's Actions tab.
