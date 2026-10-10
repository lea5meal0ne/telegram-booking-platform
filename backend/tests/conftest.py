import os

os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("DEV_AUTH", "true")
os.environ.setdefault("ADMIN_IDS", "900")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:test-only-password@127.0.0.1:55432/postgres")
os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:56379/15")
os.environ.setdefault("BOT_TOKEN", "123456789:unit-test-token-not-a-real-secret")
import pytest_asyncio
from sqlalchemy import text
from app.db import engine, Session
from app.models import User, Business, Service, Schedule
from app.auth import redis


@pytest_asyncio.fixture(autouse=True)
async def clean_database():
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE users, services, schedule_rules, appointments, appointment_history, reviews, portfolio_categories, portfolio_items, support_conversations, support_messages, notification_jobs, business_settings RESTART IDENTITY CASCADE"
            )
        )
    await redis.flushdb()
    yield
    await engine.dispose()
    await redis.aclose()


@pytest_asyncio.fixture
async def db():
    async with Session() as session:
        yield session


@pytest_asyncio.fixture
async def seed(db):
    business = Business(id=1)
    customer = User(id=100, name="Customer", language="en")
    admin = User(id=900, name="Administrator", language="ru")
    other = User(id=200, name="Other", language="ru")
    service = Service(name={"ru": "Услуга", "en": "Service"}, description={}, duration=60, price=10000)
    db.add_all([business, customer, admin, other, service])
    db.add_all([Schedule(weekday=i, start="09:00", end="18:00") for i in range(7)])
    await db.commit()
    return customer, admin, other, service
