import asyncio
import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from unittest.mock import AsyncMock
import pytest
from fastapi import HTTPException
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from app import services as logic
from app.auth import verify_init_data, resolve_user, redis, exchange
from app.api import app
from app.config import Settings, settings
from app.db import Session
from app.models import Appointment, Job
from app.schemas import BookingInput, ReviewInput, MessageInput, ScheduleInput
from app.i18n import detect_language, tr, content, TEXT
from app.notifications import process_one, deliver

UTC = timezone.utc


def launch(user=None, timestamp=None, token=None):
    data = {
        "auth_date": str(timestamp or int(time.time())),
        "user": json.dumps(user or {"id": 100, "first_name": "Test", "language_code": "en"}),
        "query_id": str(time.time_ns()),
    }
    secret = hmac.new(b"WebAppData", (token or settings().bot_token).encode(), hashlib.sha256).digest()
    check = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    data["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(data)


async def future(db, service):
    day = (datetime.now(UTC) + timedelta(days=2)).date()
    return (await logic.slots(db, service.id, day))[0]


async def booking(db, seed):
    user, admin, other, service = seed
    start = await future(db, service)
    return await logic.book(
        db, user, BookingInput(service_id=service.id, start=start, request_key="request-key-12345678")
    )


@pytest.mark.parametrize("code,expected", [(None, "ru"), ("ru", "ru"), ("ru-RU", "ru"), ("en", "en"), ("fr", "en")])
async def test_language_detection(code, expected):
    assert detect_language(code) == expected


async def test_auth_valid():
    assert verify_init_data(launch(), settings().bot_token)["id"] == 100


@pytest.mark.parametrize("variant", ["tampered", "expired", "future", "duplicate", "missing"])
async def test_auth_invalid(variant):
    raw = launch()
    if variant == "tampered":
        raw = raw.replace("Test", "Fake")
    if variant == "expired":
        raw = launch(timestamp=int(time.time()) - 4000)
    if variant == "future":
        raw = launch(timestamp=int(time.time()) + 200)
    if variant == "duplicate":
        raw += "&auth_date=1"
    if variant == "missing":
        raw = "auth_date=1"
    with pytest.raises(HTTPException) as error:
        verify_init_data(raw, settings().bot_token)
    assert error.value.status_code == 401


async def test_auth_replay_and_language_persistence(db):
    raw = launch()
    token, user = await exchange(db, raw)
    assert await redis.get(f"session:{token}") == "100"
    user.language = "ru"
    user.explicit_language = True
    await db.commit()
    resolved = await resolve_user(db, {"id": 100, "first_name": "Test", "language_code": "en"})
    assert resolved.language == "ru"
    with pytest.raises(HTTPException):
        await exchange(db, raw)


async def test_production_rejects_dev_auth():
    with pytest.raises(ValueError):
        Settings(environment="production", dev_auth=True)


async def test_translation_parity_and_fallback():
    import string

    for pair in TEXT.values():

        def keys(value):
            return {field for _, field, _, _ in string.Formatter().parse(value) if field}

        assert keys(pair[0]) == keys(pair[1])
    assert content({"ru": "Русский", "en": ""}, "en") == "Русский"
    assert tr("forbidden", "ru") != tr("forbidden", "en")


async def test_availability_buffers_breaks_and_horizon(db, seed):
    user, admin, other, service = seed
    day = (datetime.now(UTC) + timedelta(days=2)).date()
    available = await logic.slots(db, service.id, day)
    assert len(available) == 17
    from app.models import Schedule

    db.add(Schedule(date=day.isoformat(), start="12:00", end="14:00", blocked=True))
    await db.commit()
    remaining = await logic.slots(db, service.id, day)
    assert len(remaining) < len(available)
    assert not await logic.slots(db, service.id, day + timedelta(days=365))
    config = await logic.business(db)
    config.data = {**config.data, "buffer_minutes": 30}
    await db.commit()
    assert len(await logic.slots(db, service.id, day)) < len(remaining)


async def test_booking_idempotency_and_snapshots(db, seed):
    a = await booking(db, seed)
    again = await logic.book(db, seed[0], BookingInput(service_id=seed[3].id, start=a.start, request_key=a.request_key))
    assert again.id == a.id
    assert a.snapshot["price"] == 10000
    assert len((await db.scalars(select(Job))).all()) == 5
    with pytest.raises(HTTPException):
        await logic.book(
            db, seed[2], BookingInput(service_id=seed[3].id, start=a.start, request_key="different-key-123456")
        )


async def test_concurrent_booking_conflict(db, seed):
    start = await future(db, seed[3])

    async def create(key):
        async with Session() as local:
            try:
                return await logic.book(
                    local, seed[0], BookingInput(service_id=seed[3].id, start=start, request_key=key)
                )
            except HTTPException as error:
                return error

    results = await asyncio.gather(create("concurrent-key-1111"), create("concurrent-key-2222"))
    assert sum(isinstance(x, Appointment) for x in results) == 1
    assert sum(isinstance(x, HTTPException) and x.status_code == 409 for x in results) == 1


async def test_database_overlap_constraint(db, seed):
    a = await booking(db, seed)
    db.add(
        Appointment(
            user_id=seed[2].id,
            service_id=seed[3].id,
            start=a.start,
            end=a.end,
            busy_end=a.busy_end,
            snapshot=a.snapshot,
            request_key="constraint-test-key",
        )
    )
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()


async def test_cancel_and_authorization(db, seed):
    a = await booking(db, seed)
    with pytest.raises(HTTPException) as error:
        await logic.cancel(db, seed[2], a.id)
    assert error.value.status_code == 403
    assert (await logic.cancel(db, seed[0], a.id)).status == "canceled"
    assert all(j.state == "canceled" for j in (await db.scalars(select(Job).where(Job.kind == "reminder"))).all())


async def test_reschedule_and_confirmations(db, seed):
    a = await booking(db, seed)
    await logic.confirm(db, seed[0], a.id)
    assert a.customer_confirmed and not a.admin_confirmed
    await logic.confirm(db, seed[1], a.id)
    assert a.admin_confirmed
    moved = utc_start = a.start + timedelta(days=1)
    await logic.reschedule(db, seed[0], a.id, moved)
    assert a.start == utc_start and not a.customer_confirmed and not a.admin_confirmed


async def past_appointment(db, seed):
    a = await booking(db, seed)
    a.start = datetime.now(UTC) - timedelta(hours=2)
    a.end = datetime.now(UTC) - timedelta(hours=1)
    a.busy_end = a.end
    await db.commit()
    return a


async def test_verified_review_and_duplicate_prevention(db, seed):
    a = await past_appointment(db, seed)
    data = ReviewInput(appointment_id=a.id, rating=5, text="Great")
    with pytest.raises(HTTPException):
        await logic.submit_review(db, seed[0], data)
    await logic.attendance(db, seed[1], a.id, "attended")
    assert a.verified_by == 900 and a.verified_at
    review = await logic.submit_review(db, seed[0], data)
    assert review.rating == 5
    with pytest.raises(HTTPException):
        await logic.submit_review(db, seed[0], data)
    with pytest.raises(HTTPException):
        await logic.attendance(db, seed[1], a.id, "attended")


async def test_no_show_and_deferred_attendance(db, seed):
    a = await past_appointment(db, seed)
    await logic.attendance(db, seed[1], a.id, "later")
    assert a.status == "booked" and not a.verified_at
    await logic.attendance(db, seed[1], a.id, "no_show")
    assert a.status == "no_show"
    with pytest.raises(HTTPException):
        await logic.submit_review(db, seed[0], ReviewInput(appointment_id=a.id, rating=5))
    assert not await db.scalar(select(Job).where(Job.kind == "review"))


async def test_reminder_restart_recovery_and_retry(db, seed):
    await booking(db, seed)
    bot = AsyncMock()
    bot.send_message.side_effect = RuntimeError("Network unavailable")
    assert await process_one(bot, datetime.now(UTC) + timedelta(days=3))
    await db.execute(text("UPDATE notification_jobs SET due=now()"))
    await db.commit()
    bot.send_message.side_effect = None
    for _ in range(6):
        await process_one(bot, datetime.now(UTC) + timedelta(days=3))
    async with Session() as recovered:
        jobs = (await recovered.scalars(select(Job))).all()
        assert all(j.state == "sent" for j in jobs)
    assert bot.send_message.call_count >= 5


async def test_localized_notifications(db, seed):
    a = await booking(db, seed)
    bot = AsyncMock()
    customer = Job(recipient_id=100, appointment_id=a.id, kind="reminder", payload={})
    admin = Job(recipient_id=900, appointment_id=a.id, kind="reminder", payload={})
    await deliver(bot, db, customer)
    assert "Reminder" in bot.send_message.call_args.args[1]
    await deliver(bot, db, admin)
    assert "Напоминание" in bot.send_message.call_args.args[1]


async def test_support_private_routing(db, seed):
    conversation = await logic.conversation_for(db, seed[0])
    await db.commit()
    await logic.send_support(db, seed[0], conversation.id, MessageInput(text="Help"))
    job = await db.scalar(select(Job))
    assert job.recipient_id == 900
    with pytest.raises(HTTPException):
        await logic.send_support(db, seed[2], conversation.id, MessageInput(text="Intrusion"))
    await logic.send_support(db, seed[1], conversation.id, MessageInput(text="Reply"))
    assert await db.scalar(select(Job.id).where(Job.recipient_id == 100, Job.kind == "support_reply"))


async def test_schedule_preserves_existing_bookings(db, seed):
    await booking(db, seed)
    with pytest.raises(HTTPException):
        await logic.safe_schedule_change(db, [])
    await logic.safe_schedule_change(db, [ScheduleInput(weekday=i, start="08:00", end="19:00") for i in range(7)])


async def client_for(user_id):
    token = f"test-session-{user_id}"
    await redis.set(f"session:{token}", str(user_id), ex=3600)
    return AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers={"Authorization": f"Bearer {token}"}
    )


async def test_api_admin_service_settings_portfolio(db, seed):
    async with await client_for(100) as customer:
        assert (await customer.get("/api/admin/services")).status_code == 403
        assert (await customer.put("/api/auth/language", json={"language": "ru"})).json()["language"] == "ru"
    async with await client_for(900) as admin:
        body = {"name": {"ru": "Тест", "en": "Test"}, "price": 25000, "duration": 45}
        response = await admin.post("/api/admin/services", json=body)
        assert response.status_code == 201
        body["price"] = 30000
        assert (await admin.put(f"/api/admin/services/{response.json()['id']}", json=body)).json()["price"] == 30000
        config = (await admin.get("/api/business")).json()
        config["address"] = "New address"
        assert (await admin.put("/api/admin/settings", json=config)).json()["address"] == "New address"
        category = (await admin.post("/api/admin/categories", json={"ru": "Категория", "en": "Category"})).json()
        portfolio = (
            await admin.post(
                "/api/admin/portfolio",
                json={"category_id": category["id"], "description": {"ru": "Описание"}, "images": []},
            )
        ).json()
        assert portfolio["id"]
        assert (await admin.delete(f"/api/admin/categories/{category['id']}")).status_code == 200
        assert (await admin.delete(f"/api/admin/portfolio/{portfolio['id']}")).status_code == 200


async def test_api_support_photo_privacy_and_error_language(db, seed):
    import io
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (10, 10)).save(buffer, "PNG")
    async with await client_for(100) as customer:
        uploaded = (
            await customer.post("/api/uploads", files={"file": ("photo.png", buffer.getvalue(), "image/png")})
        ).json()["url"]
        conversation = (await customer.get("/api/support")).json()
        assert (
            await customer.post(
                f"/api/support/{conversation['id']}/messages", json={"text": "Photo", "image": uploaded}
            )
        ).status_code == 201
        assert (await customer.get(uploaded)).status_code == 403
        assert (await customer.get(uploaded.replace("/media/", "/private-media/"))).status_code == 200
        denied = await customer.get("/api/admin/dashboard")
        assert denied.json()["message"] == "Access denied."
    async with await client_for(200) as other:
        assert (await other.get(uploaded.replace("/media/", "/private-media/"))).status_code == 403
        assert (await other.get(f"/api/support/{conversation['id']}/messages")).status_code == 403


async def test_immediate_reminder(db, seed):
    a = await booking(db, seed)
    await logic.invalidate_jobs(db, a.id)
    a.start = datetime.now(UTC) + timedelta(hours=1)
    a.end = a.start + timedelta(hours=1)
    a.busy_end = a.end
    await logic.appointment_jobs(db, a)
    await db.commit()
    jobs = (await db.scalars(select(Job).where(Job.kind == "reminder", Job.state == "pending"))).all()
    assert all(logic.utc(j.due) <= datetime.now(UTC) + timedelta(seconds=2) for j in jobs)


async def test_rescheduling_preserves_historical_duration_after_service_edit(db, seed):
    appointment = await booking(db, seed)
    seed[3].duration = 30
    seed[3].price = 20000
    await db.commit()
    moved = await logic.reschedule(db, seed[0], appointment.id, appointment.start + timedelta(days=1))
    assert moved.end - moved.start == timedelta(minutes=60)
    assert moved.snapshot["price"] == 10000


async def test_disabled_bot_token_rejects_authentication():
    with pytest.raises(HTTPException):
        verify_init_data(launch(), "")


async def test_invalid_settings_and_uploads_are_validation_errors(db, seed):
    async with await client_for(900) as admin:
        config = (await admin.get("/api/business")).json()
        config["timezone"] = "Not/A/Timezone"
        assert (await admin.put("/api/admin/settings", json=config)).status_code == 422
        config["timezone"] = "Europe/Moscow"
        config["website"] = "https://"
        assert (await admin.put("/api/admin/settings", json=config)).status_code == 422
        assert (
            await admin.post("/api/uploads", files={"file": ("bad.jpg", b"not-an-image", "image/jpeg")})
        ).status_code == 422


async def test_support_history_pagination_returns_latest_and_older_messages(db, seed):
    conversation = await logic.conversation_for(db, seed[0])
    await db.commit()
    from app.models import Message

    db.add_all([Message(conversation_id=conversation.id, sender_id=100, text=str(i)) for i in range(120)])
    await db.commit()
    async with await client_for(100) as customer:
        latest = (await customer.get(f"/api/support/{conversation.id}/messages?limit=50")).json()
        assert latest[-1]["text"] == "119"
        older = (
            await customer.get(f"/api/support/{conversation.id}/messages?limit=50&before_id={latest[0]['id']}")
        ).json()
        assert older[-1]["text"] == "69"


async def test_rate_limit_cannot_be_bypassed_with_arbitrary_bearer_headers():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for attempt in range(61):
            result = await client.post(
                "/api/auth/telegram",
                json={"init_data": "invalid"},
                headers={"Authorization": f"Bearer unknown-{attempt}", "Accept-Language": "en"},
            )
        assert result.status_code == 429
        assert result.json()["message"] == "Too many requests. Try again later."
