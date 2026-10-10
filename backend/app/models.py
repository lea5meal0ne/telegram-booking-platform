from datetime import datetime, timezone
from sqlalchemy import BigInteger, String, ForeignKey, UniqueConstraint, CheckConstraint, JSON, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base


def now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(200))
    language: Mapped[str] = mapped_column(String(2), default="ru")
    explicit_language: Mapped[bool] = mapped_column(default=False)
    deletion_requested: Mapped[bool] = mapped_column(default=False)


class Business(Base):
    __tablename__ = "business_settings"
    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    data: Mapped[dict] = mapped_column(
        JSON,
        default=lambda: {
            "name": {"ru": "Запись онлайн", "en": "Online booking"},
            "description": {"ru": "", "en": ""},
            "timezone": "Europe/Moscow",
            "currency": "RUB",
            "accent": "#5367db",
            "address": "",
            "phone": "",
            "telegram": "",
            "website": "",
            "social_links": [],
            "logo": "",
            "cover": "",
            "horizon_days": 60,
            "notice_minutes": 60,
            "cancel_minutes": 120,
            "slot_minutes": 30,
            "buffer_minutes": 0,
            "reminder_hours": 24,
        },
    )


class Service(Base):
    __tablename__ = "services"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[dict] = mapped_column(JSON)
    description: Mapped[dict] = mapped_column(JSON, default=dict)
    price: Mapped[int] = mapped_column(default=0)
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    duration: Mapped[int] = mapped_column(default=60)
    image: Mapped[str] = mapped_column(default="")
    active: Mapped[bool] = mapped_column(default=True)
    position: Mapped[int] = mapped_column(default=0)
    __table_args__ = (CheckConstraint("duration > 0 AND price >= 0"),)


class Schedule(Base):
    __tablename__ = "schedule_rules"
    id: Mapped[int] = mapped_column(primary_key=True)
    weekday: Mapped[int | None] = mapped_column(nullable=True)
    date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    start: Mapped[str] = mapped_column(String(5), default="09:00")
    end: Mapped[str] = mapped_column(String(5), default="18:00")
    blocked: Mapped[bool] = mapped_column(default=False)


class Appointment(Base):
    __tablename__ = "appointments"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"))
    start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    busy_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(default="booked", index=True)
    snapshot: Mapped[dict] = mapped_column(JSON)
    customer_confirmed: Mapped[bool] = mapped_column(default=False)
    admin_confirmed: Mapped[bool] = mapped_column(default=False)
    verified_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    request_key: Mapped[str] = mapped_column(String(100), unique=True)
    __table_args__ = (CheckConstraint('"end" > start AND busy_end >= "end"'),)


class History(Base):
    __tablename__ = "appointment_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    appointment_id: Mapped[int] = mapped_column(ForeignKey("appointments.id"), index=True)
    actor_id: Mapped[int] = mapped_column(BigInteger)
    action: Mapped[str] = mapped_column(String(100))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Review(Base):
    __tablename__ = "reviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    appointment_id: Mapped[int] = mapped_column(ForeignKey("appointments.id"), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    rating: Mapped[int] = mapped_column()
    text: Mapped[str] = mapped_column(Text, default="")
    anonymous: Mapped[bool] = mapped_column(default=False)
    visible: Mapped[bool] = mapped_column(default=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (CheckConstraint("rating BETWEEN 1 AND 5"),)


class Category(Base):
    __tablename__ = "portfolio_categories"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[dict] = mapped_column(JSON)


class Portfolio(Base):
    __tablename__ = "portfolio_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("portfolio_categories.id", ondelete="SET NULL"), nullable=True
    )
    description: Mapped[dict] = mapped_column(JSON, default=dict)
    images: Mapped[list] = mapped_column(JSON, default=list)
    position: Mapped[int] = mapped_column(default=0)


class Conversation(Base):
    __tablename__ = "support_conversations"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(default="open")


class Message(Base):
    __tablename__ = "support_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("support_conversations.id"), index=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    text: Mapped[str] = mapped_column(Text, default="")
    image: Mapped[str] = mapped_column(default="")
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Job(Base):
    __tablename__ = "notification_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    appointment_id: Mapped[int | None] = mapped_column(ForeignKey("appointments.id"), nullable=True)
    recipient_id: Mapped[int] = mapped_column(BigInteger)
    kind: Mapped[str] = mapped_column(String(50))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    due: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    state: Mapped[str] = mapped_column(default="pending", index=True)
    attempts: Mapped[int] = mapped_column(default=0)
    key: Mapped[str] = mapped_column(String(200), unique=True)
    __table_args__ = (UniqueConstraint("key"),)
