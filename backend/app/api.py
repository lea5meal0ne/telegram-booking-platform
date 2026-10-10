import io
import secrets
from datetime import date, timedelta
from pathlib import Path
from typing import Literal
from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from app import services as logic
from app.auth import administrator, current_user, exchange, redis, resolve_user
from app.config import settings
from app.db import session
from app.i18n import tr
from app.models import User, Service, Schedule, Appointment, Review, Portfolio, Category, Conversation, Message, History
from app.schemas import (
    ServiceInput,
    BookingInput,
    MoveInput,
    ScheduleInput,
    ReviewInput,
    MessageInput,
    PortfolioInput,
    Localized,
    BusinessInput,
    ServiceOutput,
    ScheduleOutput,
    AppointmentOutput,
    PortfolioOutput,
    CategoryOutput,
    ConversationOutput,
    MessageOutput,
)

from app.logging import configure_logging

configure_logging()
app = FastAPI(
    title="Telegram Booking Platform",
    version="1.0.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url=None,
)


@app.exception_handler(HTTPException)
async def http_error(request, error):
    key = error.detail if isinstance(error.detail, str) else "invalid"
    return JSONResponse(
        status_code=error.status_code,
        content={"code": key, "message": tr(key, getattr(request.state, "language", "ru"))},
    )


@app.exception_handler(IntegrityError)
async def integrity_error(request, error):
    return JSONResponse(
        status_code=409,
        content={"code": "conflict", "message": tr("conflict", getattr(request.state, "language", "ru"))},
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request, error):
    return JSONResponse(
        status_code=422, content={"code": "invalid", "message": tr("invalid", getattr(request.state, "language", "ru"))}
    )


@app.middleware("http")
async def security(request: Request, call_next):
    request.state.language = "en" if request.headers.get("accept-language", "ru").startswith("en") else "ru"
    if request.url.path.startswith("/api") and request.method != "GET":
        # Unknown bearer strings must not let anonymous callers bypass their IP quota.
        import hashlib

        try:
            identity = request.client.host if request.client else "unknown"
            authorization = request.headers.get("authorization", "")
            if authorization.startswith("Bearer "):
                identifier = await redis.get(f"session:{authorization[7:]}")
                if identifier:
                    identity = f"user:{identifier}"
            key = "rate:" + hashlib.sha256(identity.encode()).hexdigest()
            count = await redis.incr(key)
            if count == 1:
                await redis.expire(key, 60)
            if count > 60:
                return JSONResponse(
                    status_code=429, content={"code": "rate_limit", "message": tr("rate_limit", request.state.language)}
                )
        except Exception:
            return JSONResponse(
                status_code=503, content={"code": "unavailable", "message": tr("unavailable", request.state.language)}
            )
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    if "/auth" in request.url.path:
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/api/health")
async def health(db: AsyncSession = Depends(session)):
    await db.execute(text("SELECT 1"))
    await redis.ping()
    return {"status": "ok"}


class AuthInput(BaseModel):
    init_data: str = Field(max_length=16384)


@app.post("/api/auth/telegram")
async def telegram_auth(data: AuthInput, db: AsyncSession = Depends(session)):
    token, user = await exchange(db, data.init_data)
    return {"token": token, "user": user_json(user)}


class DevInput(BaseModel):
    user_id: int = Field(default=100, gt=0)
    language: Literal["ru", "en"] = "ru"


@app.post("/api/auth/development", include_in_schema=False)
async def development_auth(data: DevInput, db: AsyncSession = Depends(session)):
    if not settings().dev_auth or settings().environment != "development":
        raise HTTPException(404, "not_found")
    user = await resolve_user(db, {"id": data.user_id, "first_name": "Local developer", "language_code": data.language})
    await db.commit()
    token = secrets.token_urlsafe(32)
    await redis.set(f"session:{token}", str(user.id), ex=86400)
    return {"token": token, "user": user_json(user)}


def user_json(user):
    return {
        "id": user.id,
        "name": user.name,
        "language": user.language,
        "is_admin": user.id in settings().admins,
        "deletion_requested": user.deletion_requested,
    }


@app.get("/api/auth/me")
async def me(user=Depends(current_user)):
    return user_json(user)


class LanguageInput(BaseModel):
    language: Literal["ru", "en"]


@app.put("/api/auth/language")
async def language(data: LanguageInput, user=Depends(current_user), db=Depends(session)):
    user.language = data.language
    user.explicit_language = True
    db.add(user)
    await db.commit()
    return user_json(user)


@app.post("/api/auth/deletion-request")
async def deletion_request(user=Depends(current_user), db=Depends(session)):
    user.deletion_requested = True
    db.add(user)
    for admin in settings().admins:
        await logic.queue(db, admin, "deletion", payload={"name": user.name, "user_id": user.id})
    await db.commit()
    return {"accepted": True}


@app.get("/api/business")
async def get_business(db=Depends(session)):
    value = (await logic.business(db)).data
    await db.commit()
    return value


@app.put("/api/admin/settings")
async def settings_update(data: BusinessInput, actor=Depends(administrator), db=Depends(session)):
    await logic.booking_lock(db)
    config = await logic.business(db)
    config.data = data.model_dump()
    await db.commit()
    return config.data


@app.get("/api/services", response_model=list[ServiceOutput])
async def get_services(db=Depends(session)):
    return (
        await db.scalars(select(Service).where(Service.active.is_(True)).order_by(Service.position, Service.id))
    ).all()


@app.get("/api/admin/services", response_model=list[ServiceOutput])
async def admin_services(actor=Depends(administrator), db=Depends(session)):
    return (await db.scalars(select(Service).order_by(Service.position, Service.id))).all()


@app.post("/api/admin/services", status_code=201, response_model=ServiceOutput)
async def add_service(data: ServiceInput, actor=Depends(administrator), db=Depends(session)):
    value = Service(**data.model_dump())
    db.add(value)
    await db.commit()
    return value


@app.put("/api/admin/services/{identifier}", response_model=ServiceOutput)
async def edit_service(identifier: int, data: ServiceInput, actor=Depends(administrator), db=Depends(session)):
    await logic.booking_lock(db)
    value = await logic.require(db, Service, identifier)
    for key, item in data.model_dump().items():
        setattr(value, key, item)
    await db.commit()
    return value


@app.delete("/api/admin/services/{identifier}")
async def delete_service(identifier: int, actor=Depends(administrator), db=Depends(session)):
    await logic.booking_lock(db)
    value = await logic.require(db, Service, identifier)
    if await db.scalar(select(Appointment.id).where(Appointment.service_id == identifier).limit(1)):
        value.active = False  # Keep historical foreign keys intact.
    else:
        await db.delete(value)
    await db.commit()
    return {"ok": True}


@app.get("/api/availability")
async def availability(service_id: int, day: date, db=Depends(session)):
    return {"slots": await logic.slots(db, service_id, day)}


@app.get("/api/availability/month")
async def availability_month(service_id: int, month: date, db=Depends(session)):
    start = month.replace(day=1)
    result = {}
    current = start
    while current.month == start.month:
        result[current.isoformat()] = len(await logic.slots(db, service_id, current))
        current += timedelta(days=1)
    return result


@app.get("/api/appointments", response_model=list[AppointmentOutput])
async def appointments(
    user=Depends(current_user),
    db=Depends(session),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status: str = "all",
):
    return (
        await db.scalars(
            select(Appointment)
            .where(Appointment.user_id == user.id)
            .where(True if status == "all" else Appointment.status == status)
            .order_by(Appointment.start.desc())
            .offset(offset)
            .limit(limit)
        )
    ).all()


@app.post("/api/appointments", status_code=201, response_model=AppointmentOutput)
async def book(data: BookingInput, user=Depends(current_user), db=Depends(session)):
    return await logic.book(db, user, data)


@app.post("/api/appointments/{identifier}/cancel", response_model=AppointmentOutput)
async def cancel(identifier: int, user=Depends(current_user), db=Depends(session)):
    return await logic.cancel(db, user, identifier)


@app.post("/api/appointments/{identifier}/reschedule", response_model=AppointmentOutput)
async def move(identifier: int, data: MoveInput, user=Depends(current_user), db=Depends(session)):
    return await logic.reschedule(db, user, identifier, data.start)


@app.post("/api/appointments/{identifier}/confirm", response_model=AppointmentOutput)
async def confirm(identifier: int, user=Depends(current_user), db=Depends(session)):
    return await logic.confirm(db, user, identifier)


class AttendanceInput(BaseModel):
    decision: Literal["attended", "no_show", "later"]


@app.post("/api/admin/appointments/{identifier}/attendance", response_model=AppointmentOutput)
async def verify(identifier: int, data: AttendanceInput, actor=Depends(administrator), db=Depends(session)):
    return await logic.attendance(db, actor, identifier, data.decision)


@app.get("/api/admin/appointments", response_model=list[AppointmentOutput])
async def all_appointments(
    actor=Depends(administrator),
    db=Depends(session),
    status: str | None = None,
    day: date | None = None,
    search: str = "",
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    query = select(Appointment, User.name).join(User, Appointment.user_id == User.id)
    if status:
        query = query.where(Appointment.status == status)
    if search:
        query = query.where(User.name.ilike(f"%{search[:200]}%"))
    if day:
        from zoneinfo import ZoneInfo
        from datetime import datetime, time

        tz = ZoneInfo((await logic.business(db)).data["timezone"])
        query = query.where(
            Appointment.start >= datetime.combine(day, time.min, tz),
            Appointment.start < datetime.combine(day + timedelta(days=1), time.min, tz),
        )
    values = (await db.execute(query.order_by(Appointment.start.desc()).offset(offset).limit(limit))).all()
    from fastapi.encoders import jsonable_encoder

    return [{**jsonable_encoder(a), "customer_name": name} for a, name in values]


@app.get("/api/admin/appointments/{identifier}/history")
async def appointment_history(identifier: int, actor=Depends(administrator), db=Depends(session)):
    return (await db.scalars(select(History).where(History.appointment_id == identifier).order_by(History.at))).all()


@app.get("/api/admin/dashboard")
async def dashboard(actor=Depends(administrator), db=Depends(session)):
    from datetime import datetime, time
    from zoneinfo import ZoneInfo

    config = (await logic.business(db)).data
    tz = ZoneInfo(config["timezone"])
    today = datetime.now(tz).date()
    start = datetime.combine(today, time.min, tz)
    end = start + timedelta(days=1)

    async def count(*conditions):
        return await db.scalar(select(func.count(Appointment.id)).where(*conditions))

    return {
        "today": await count(Appointment.start >= start, Appointment.start < end),
        "upcoming": await count(Appointment.status == "booked", Appointment.start >= datetime.now(logic.UTC)),
        "pending": await count(Appointment.status == "booked", Appointment.customer_confirmed.is_(False)),
        "unverified": await count(Appointment.status == "booked", Appointment.end <= datetime.now(logic.UTC)),
        "completed": await count(Appointment.status == "completed"),
        "messages": await db.scalar(select(func.count(Conversation.id)).where(Conversation.status == "open")),
        "rating": await db.scalar(select(func.avg(Review.rating)).where(Review.visible.is_(True))) or 0,
    }


@app.get("/api/admin/schedule", response_model=list[ScheduleOutput])
async def get_schedule(actor=Depends(administrator), db=Depends(session)):
    return (await db.scalars(select(Schedule))).all()


@app.put("/api/admin/schedule")
async def set_schedule(data: list[ScheduleInput], actor=Depends(administrator), db=Depends(session)):
    if len(data) > 1000:
        raise HTTPException(422, "invalid")
    await logic.safe_schedule_change(db, data)
    return {"ok": True}


@app.get("/api/reviews")
async def reviews(db=Depends(session), offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
    rows = (
        await db.execute(
            select(Review, User.name)
            .join(User)
            .where(Review.visible.is_(True))
            .order_by(Review.at.desc())
            .offset(offset)
            .limit(limit)
        )
    ).all()
    from fastapi.encoders import jsonable_encoder

    items = [
        {k: v for k, v in jsonable_encoder(review).items() if k not in {"user_id", "appointment_id"}}
        | {"name": "" if review.anonymous else name}
        for review, name in rows
    ]
    distribution = dict(
        (
            await db.execute(
                select(Review.rating, func.count()).where(Review.visible.is_(True)).group_by(Review.rating)
            )
        ).all()
    )
    total = sum(distribution.values())
    return {
        "items": items,
        "total": total,
        "average": sum(k * v for k, v in distribution.items()) / total if total else 0,
        "distribution": distribution,
    }


@app.post("/api/reviews", status_code=201)
async def review(data: ReviewInput, user=Depends(current_user), db=Depends(session)):
    return await logic.submit_review(db, user, data)


class ModerationInput(BaseModel):
    visible: bool


@app.put("/api/admin/reviews/{identifier}")
async def moderate(identifier: int, data: ModerationInput, actor=Depends(administrator), db=Depends(session)):
    review = await logic.require(db, Review, identifier)
    review.visible = data.visible
    await db.commit()
    return {"ok": True}


@app.get("/api/admin/reviews")
async def admin_reviews(
    actor=Depends(administrator),
    db=Depends(session),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    return (await db.scalars(select(Review).order_by(Review.at.desc()).offset(offset).limit(limit))).all()


@app.get("/api/portfolio", response_model=list[PortfolioOutput])
async def portfolio(
    db=Depends(session),
    category_id: int | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    query = select(Portfolio).order_by(Portfolio.position, Portfolio.id)
    if category_id:
        query = query.where(Portfolio.category_id == category_id)
    return (await db.scalars(query.offset(offset).limit(limit))).all()


@app.get("/api/portfolio/categories", response_model=list[CategoryOutput])
async def categories(db=Depends(session)):
    return (await db.scalars(select(Category).order_by(Category.id))).all()


@app.post("/api/admin/portfolio", status_code=201)
async def portfolio_add(data: PortfolioInput, actor=Depends(administrator), db=Depends(session)):
    if data.category_id:
        await logic.require(db, Category, data.category_id)
    item = Portfolio(**data.model_dump())
    db.add(item)
    await db.commit()
    return item


@app.put("/api/admin/portfolio/{identifier}")
async def portfolio_edit(identifier: int, data: PortfolioInput, actor=Depends(administrator), db=Depends(session)):
    item = await logic.require(db, Portfolio, identifier)
    if data.category_id:
        await logic.require(db, Category, data.category_id)
    for key, value in data.model_dump().items():
        setattr(item, key, value)
    await db.commit()
    return item


@app.delete("/api/admin/portfolio/{identifier}")
async def portfolio_delete(identifier: int, actor=Depends(administrator), db=Depends(session)):
    await db.delete(await logic.require(db, Portfolio, identifier))
    await db.commit()
    return {"ok": True}


@app.post("/api/admin/categories", status_code=201)
async def category_add(data: Localized, actor=Depends(administrator), db=Depends(session)):
    item = Category(name=data.model_dump())
    db.add(item)
    await db.commit()
    return item


@app.put("/api/admin/categories/{identifier}")
async def category_edit(identifier: int, data: Localized, actor=Depends(administrator), db=Depends(session)):
    item = await logic.require(db, Category, identifier)
    item.name = data.model_dump()
    await db.commit()
    return item


@app.delete("/api/admin/categories/{identifier}")
async def category_delete(identifier: int, actor=Depends(administrator), db=Depends(session)):
    await db.delete(await logic.require(db, Category, identifier))
    await db.commit()
    return {"ok": True}


@app.get("/api/support", response_model=ConversationOutput)
async def support(user=Depends(current_user), db=Depends(session)):
    conversation = await logic.conversation_for(db, user)
    await db.commit()
    return conversation


@app.get("/api/admin/support", response_model=list[ConversationOutput])
async def support_inbox(
    actor=Depends(administrator),
    db=Depends(session),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    from fastapi.encoders import jsonable_encoder

    rows = (
        await db.execute(
            select(Conversation, User.name).join(User).order_by(Conversation.id.desc()).offset(offset).limit(limit)
        )
    ).all()
    return [{**jsonable_encoder(c), "name": name} for c, name in rows]


@app.get("/api/support/{identifier}/messages", response_model=list[MessageOutput])
async def support_messages(
    identifier: int,
    user=Depends(current_user),
    db=Depends(session),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    before_id: int | None = Query(None, gt=0),
):
    conversation = await logic.require(db, Conversation, identifier)
    if user.id not in settings().admins and conversation.user_id != user.id:
        raise HTTPException(403, "forbidden")
    values = (
        await db.scalars(
            select(Message)
            .where(Message.conversation_id == identifier)
            .where(True if before_id is None else Message.id < before_id)
            .order_by(Message.id.desc())
            .offset(offset)
            .limit(limit)
        )
    ).all()

    return list(reversed(values))


@app.post("/api/support/{identifier}/messages", status_code=201, response_model=MessageOutput)
async def support_send(identifier: int, data: MessageInput, user=Depends(current_user), db=Depends(session)):
    return await logic.send_support(db, user, identifier, data)


class ConversationInput(BaseModel):
    status: Literal["open", "closed"]


@app.put("/api/admin/support/{identifier}")
async def support_status(identifier: int, data: ConversationInput, actor=Depends(administrator), db=Depends(session)):
    conversation = await logic.require(db, Conversation, identifier)
    conversation.status = data.status
    await db.commit()
    return conversation


async def store_image(data: bytes):
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(413, "invalid")
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.width * image.height > 20000000:
                raise ValueError("Image too large")
            image = image.convert("RGB")
            image.thumbnail((2000, 2000))
            identifier = secrets.token_hex(16) + ".jpg"
            root = Path(settings().uploads_dir)
            root.mkdir(parents=True, exist_ok=True)
            image.save(root / identifier, "JPEG", quality=85)
    except (UnidentifiedImageError, ValueError, OSError, Image.DecompressionBombError) as error:
        raise HTTPException(422, "invalid") from error
    return f"/api/media/{identifier}"


@app.post("/api/uploads")
async def upload(file: UploadFile = File(), user=Depends(current_user)):
    return {"url": await store_image(await file.read(8 * 1024 * 1024 + 1))}


@app.get("/api/media/{filename}")
async def media(filename: str):
    import re

    if not re.fullmatch(r"[a-f0-9]{32}\.jpg", filename):
        raise HTTPException(404, "not_found")
    # Support attachments are not exposed through this public route.
    async with __import__("app.db", fromlist=["Session"]).Session() as db:
        from sqlalchemy import cast, String

        url = f"/api/media/{filename}"
        public = await db.scalar(select(Portfolio.id).where(cast(Portfolio.images, String).contains(url)).limit(1))
        public = public or await db.scalar(select(Service.id).where(Service.image == url).limit(1))
        config = (await logic.business(db)).data
        if not public and url not in {config.get("logo"), config.get("cover")}:
            raise HTTPException(403, "forbidden")
    path = Path(settings().uploads_dir) / filename
    if not path.is_file():
        raise HTTPException(404, "not_found")
    return FileResponse(path, media_type="image/jpeg")


@app.get("/api/private-media/{filename}")
async def private_media(filename: str, user=Depends(current_user), db=Depends(session)):
    import re

    if not re.fullmatch(r"[a-f0-9]{32}\.jpg", filename):
        raise HTTPException(404, "not_found")
    if user.id not in settings().admins:
        allowed = await db.scalar(
            select(Message.id)
            .join(Conversation)
            .where(Message.image == f"/api/media/{filename}", Conversation.user_id == user.id)
            .limit(1)
        )
        if not allowed:
            raise HTTPException(403, "forbidden")
    path = Path(settings().uploads_dir) / filename
    if not path.is_file():
        raise HTTPException(404, "not_found")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, no-store"})


@app.get("/api/admin/notifications")
async def failed_notifications(actor=Depends(administrator), db=Depends(session), offset: int = Query(0, ge=0)):
    from app.models import Job

    return (
        await db.scalars(select(Job).where(Job.state == "failed").order_by(Job.id.desc()).offset(offset).limit(50))
    ).all()


@app.post("/api/admin/notifications/{identifier}/retry")
async def retry_notification(identifier: int, actor=Depends(administrator), db=Depends(session)):
    from app.models import Job
    from datetime import datetime

    await logic.booking_lock(db)
    job = await logic.require(db, Job, identifier)
    if job.state != "failed":
        raise HTTPException(409, "duplicate")
    job.state = "pending"
    job.attempts = 0
    job.due = datetime.now(logic.UTC)
    await db.commit()
    return {"ok": True}


@app.get("/api/admin/deletion-requests")
async def deletion_requests(actor=Depends(administrator), db=Depends(session)):
    return [
        {"id": user.id, "name": user.name}
        for user in (await db.scalars(select(User).where(User.deletion_requested.is_(True)))).all()
    ]


@app.get("/api/appointments/{identifier}", response_model=AppointmentOutput)
async def appointment_detail(identifier: int, user=Depends(current_user), db=Depends(session)):
    return await logic.owned_appointment(db, identifier, user)


@app.get("/api/appointments/{identifier}/availability")
async def reschedule_availability(identifier: int, day: date, user=Depends(current_user), db=Depends(session)):
    appointment = await logic.owned_appointment(db, identifier, user)
    return {
        "slots": await logic.slots(
            db, appointment.service_id, day, exclude=identifier, duration_override=appointment.snapshot["duration"]
        )
    }


@app.get("/api/appointments/{identifier}/availability/month")
async def reschedule_month(identifier: int, month: date, user=Depends(current_user), db=Depends(session)):
    appointment = await logic.owned_appointment(db, identifier, user)
    current = month.replace(day=1)
    result = {}
    while current.month == month.month:
        result[current.isoformat()] = len(
            await logic.slots(
                db,
                appointment.service_id,
                current,
                exclude=identifier,
                duration_override=appointment.snapshot["duration"],
            )
        )
        current += timedelta(days=1)
    return result
