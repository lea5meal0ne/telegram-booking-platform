from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError
from app.models import Appointment, Business, Service, Schedule, History, Job, Review, Conversation, Message
from app.config import settings
from app.repositories import get_or_404

UTC = timezone.utc


def utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


async def business(db):
    result = await db.get(Business, 1)
    if not result:
        result = Business(id=1)
        db.add(result)
        await db.flush()
    return result


async def booking_lock(db):
    if db.bind.dialect.name == "postgresql":
        await db.execute(text("SELECT pg_advisory_xact_lock(18473920)"))


async def require(db, model, identifier):
    return await get_or_404(db, model, identifier)


async def owned_appointment(db, identifier, actor):
    result = await require(db, Appointment, identifier)
    if result.user_id != actor.id and actor.id not in settings().admins:
        raise HTTPException(403, "forbidden")
    return result


async def slots(db, service_id, day: date, exclude=None, clock=None, duration_override=None):
    svc = await require(db, Service, service_id)
    if not svc.active and not exclude:
        return []
    config = (await business(db)).data
    tz = ZoneInfo(config["timezone"])
    clock = utc(clock or datetime.now(UTC))
    local_today = clock.astimezone(tz).date()
    if day < local_today or day > local_today + timedelta(days=config["horizon_days"]):
        return []
    rules = (
        await db.scalars(
            select(Schedule).where((Schedule.weekday == day.weekday()) | (Schedule.date == day.isoformat()))
        )
    ).all()
    specific = [r for r in rules if r.date == day.isoformat()]
    windows = [
        r
        for r in (specific if any(not r.blocked for r in specific) else rules)
        if not r.blocked and (r.date == day.isoformat() or r.weekday == day.weekday())
    ]
    blocks = [r for r in rules if r.blocked]
    start_day = datetime.combine(day, time.min, tz).astimezone(UTC)
    end_day = datetime.combine(day + timedelta(days=1), time.min, tz).astimezone(UTC)
    query = select(Appointment).where(
        Appointment.status == "booked", Appointment.start < end_day, Appointment.busy_end > start_day
    )
    if exclude:
        query = query.where(Appointment.id != exclude)
    occupied = (await db.scalars(query)).all()
    duration = timedelta(minutes=duration_override or svc.duration)
    buffer = timedelta(minutes=config["buffer_minutes"])
    notice = clock + timedelta(minutes=config["notice_minutes"])
    results = set()
    for window in windows:
        begin = datetime.combine(day, time.fromisoformat(window.start), tz)
        finish = datetime.combine(day, time.fromisoformat(window.end), tz)
        candidate = begin
        while candidate + duration + buffer <= finish:
            start = candidate.astimezone(UTC)
            end = start + duration + buffer
            local_roundtrip = start.astimezone(tz)
            valid = local_roundtrip.replace(tzinfo=None) == candidate.replace(tzinfo=None)
            blocked = any(
                start < datetime.combine(day, time.fromisoformat(r.end), tz).astimezone(UTC)
                and end > datetime.combine(day, time.fromisoformat(r.start), tz).astimezone(UTC)
                for r in blocks
            )
            conflict = any(start < utc(a.busy_end) and end > utc(a.start) for a in occupied)
            if valid and start >= notice and not blocked and not conflict:
                results.add(start)
            candidate += timedelta(minutes=config["slot_minutes"])
    return sorted(results)


async def queue(db, recipient, kind, appointment=None, due=None, payload=None, key=None):
    job = Job(
        recipient_id=recipient,
        kind=kind,
        appointment_id=appointment.id if appointment else None,
        due=due or datetime.now(UTC),
        payload=payload or {},
        key=key or uuid4().hex,
    )
    db.add(job)


async def appointment_jobs(db, appointment, changed=False):
    config = (await business(db)).data
    due = max(datetime.now(UTC), utc(appointment.start) - timedelta(hours=config["reminder_hours"]))
    for recipient in {appointment.user_id, *settings().admins}:
        await queue(db, recipient, "changed" if changed else "booking", appointment)
        await queue(db, recipient, "reminder", appointment, due=due)
    for recipient in settings().admins:
        await queue(db, recipient, "attendance", appointment, due=utc(appointment.end))


async def history(db, appointment, actor, action):
    db.add(History(appointment_id=appointment.id, actor_id=actor.id, action=action))


async def book(db, actor, data):
    await booking_lock(db)
    existing = await db.scalar(select(Appointment).where(Appointment.request_key == data.request_key))
    if existing:
        if existing.user_id != actor.id:
            raise HTTPException(409, "duplicate")
        return existing
    svc = await require(db, Service, data.service_id)
    config = (await business(db)).data
    start = utc(data.start)
    day = start.astimezone(ZoneInfo(config["timezone"])).date()
    if start not in await slots(db, svc.id, day):
        raise HTTPException(409, "conflict")
    appointment = Appointment(
        user_id=actor.id,
        service_id=svc.id,
        start=start,
        end=start + timedelta(minutes=svc.duration),
        busy_end=start + timedelta(minutes=svc.duration + config["buffer_minutes"]),
        request_key=data.request_key,
        snapshot={"name": svc.name, "price": svc.price, "currency": svc.currency, "duration": svc.duration},
    )
    db.add(appointment)
    try:
        await db.flush()
        await history(db, appointment, actor, "booked")
        await appointment_jobs(db, appointment)
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        raise HTTPException(409, "conflict") from error
    return appointment


async def cancel(db, actor, identifier):
    await booking_lock(db)
    appointment = await owned_appointment(db, identifier, actor)
    if appointment.status == "canceled":
        return appointment
    await change_allowed(db, appointment, actor)
    appointment.status = "canceled"
    await invalidate_jobs(db, appointment.id)
    await history(db, appointment, actor, "canceled")
    for recipient in {appointment.user_id, *settings().admins}:
        await queue(db, recipient, "canceled", appointment)
    await db.commit()
    return appointment


async def change_allowed(db, appointment, actor):
    if appointment.status != "booked":
        raise HTTPException(409, "duplicate")
    config = (await business(db)).data
    if actor.id not in settings().admins and utc(appointment.start) < datetime.now(UTC) + timedelta(
        minutes=config["cancel_minutes"]
    ):
        raise HTTPException(409, "cancellation_closed")


async def invalidate_jobs(db, identifier):
    await db.execute(
        update(Job).where(Job.appointment_id == identifier, Job.state == "pending").values(state="canceled")
    )


async def reschedule(db, actor, identifier, start):
    await booking_lock(db)
    appointment = await owned_appointment(db, identifier, actor)
    await change_allowed(db, appointment, actor)
    config = (await business(db)).data
    start = utc(start)
    day = start.astimezone(ZoneInfo(config["timezone"])).date()
    if start not in await slots(
        db, appointment.service_id, day, exclude=identifier, duration_override=appointment.snapshot["duration"]
    ):
        raise HTTPException(409, "conflict")
    duration = appointment.snapshot["duration"]
    await invalidate_jobs(db, identifier)
    previous = utc(appointment.start).isoformat()
    appointment.start = start
    appointment.end = start + timedelta(minutes=duration)
    appointment.busy_end = appointment.end + timedelta(minutes=config["buffer_minutes"])
    appointment.customer_confirmed = False
    appointment.admin_confirmed = False
    await history(db, appointment, actor, f"rescheduled from {previous}")
    await appointment_jobs(db, appointment, changed=True)
    await db.commit()
    return appointment


async def confirm(db, actor, identifier):
    await booking_lock(db)
    appointment = await owned_appointment(db, identifier, actor)
    if appointment.status != "booked":
        raise HTTPException(409, "duplicate")
    if actor.id == appointment.user_id:
        appointment.customer_confirmed = True
    if actor.id in settings().admins:
        appointment.admin_confirmed = True
    await history(db, appointment, actor, "confirmed")
    await db.commit()
    return appointment


async def attendance(db, actor, identifier, decision):
    if actor.id not in settings().admins:
        raise HTTPException(403, "forbidden")
    await booking_lock(db)
    appointment = await require(db, Appointment, identifier)
    if appointment.status != "booked" or utc(appointment.end) > datetime.now(UTC):
        raise HTTPException(409, "duplicate")
    if decision == "later":
        await history(db, appointment, actor, "attendance deferred")
        await queue(db, actor.id, "attendance", appointment, due=datetime.now(UTC) + timedelta(hours=2))
    else:
        appointment.status = "completed" if decision == "attended" else "no_show"
        appointment.verified_by = actor.id
        appointment.verified_at = datetime.now(UTC)
        await invalidate_jobs(db, identifier)
        await history(db, appointment, actor, appointment.status)
        if decision == "attended":
            await queue(db, appointment.user_id, "review", appointment)
    await db.commit()
    return appointment


async def submit_review(db, actor, data):
    await booking_lock(db)
    appointment = await owned_appointment(db, data.appointment_id, actor)
    if appointment.user_id != actor.id or appointment.status != "completed" or not appointment.verified_at:
        raise HTTPException(403, "review_ineligible")
    if await db.scalar(select(Review).where(Review.appointment_id == appointment.id)):
        raise HTTPException(409, "duplicate")
    review = Review(user_id=actor.id, **data.model_dump())
    db.add(review)
    await db.commit()
    return review


async def conversation_for(db, actor):
    result = await db.scalar(
        select(Conversation).where(Conversation.user_id == actor.id).order_by(Conversation.id.desc())
    )
    if not result:
        result = Conversation(user_id=actor.id)
        db.add(result)
        await db.flush()
    return result


async def send_support(db, actor, identifier, data):
    conversation = await require(db, Conversation, identifier)
    admin = actor.id in settings().admins
    if not admin and conversation.user_id != actor.id:
        raise HTTPException(403, "forbidden")
    conversation.status = "open"
    message = Message(conversation_id=identifier, sender_id=actor.id, **data.model_dump())
    db.add(message)
    await db.flush()
    recipients = {conversation.user_id} if admin else settings().admins
    for recipient in recipients:
        await queue(
            db,
            recipient,
            "support_reply" if admin else "support_message",
            payload={"conversation": identifier, "text": message.text, "image": message.image},
        )
    await db.commit()
    return message


async def safe_schedule_change(db, rules):
    await booking_lock(db)
    appointments = (
        await db.scalars(
            select(Appointment).where(Appointment.status == "booked", Appointment.start > datetime.now(UTC))
        )
    ).all()
    config = (await business(db)).data
    tz = ZoneInfo(config["timezone"])
    # Never silently change availability for an existing appointment.
    for a in appointments:
        day = utc(a.start).astimezone(tz).date()
        start = utc(a.start).astimezone(tz).strftime("%H:%M")
        end = utc(a.busy_end).astimezone(tz).strftime("%H:%M")
        relevant = [r for r in rules if r.date == day.isoformat() or r.weekday == day.weekday()]
        specific = [r for r in relevant if r.date and not r.blocked]
        working = specific or [r for r in relevant if not r.blocked]
        if not any(r.start <= start and r.end >= end for r in working) or any(
            r.blocked and start < r.end and end > r.start for r in relevant
        ):
            raise HTTPException(409, "conflict")
    from sqlalchemy import delete

    await db.execute(delete(Schedule))
    db.add_all([Schedule(**r.model_dump()) for r in rules])
    await db.commit()
