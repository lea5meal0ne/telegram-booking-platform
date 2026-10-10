import hashlib
import hmac
import json
import secrets
import time
from urllib.parse import parse_qsl
from fastapi import Depends, Header, HTTPException, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.config import settings
from app.db import session
from app.models import User
from app.i18n import detect_language

redis = Redis.from_url(settings().redis_url, decode_responses=True)


def verify_init_data(raw: str, token: str, max_age=3600, timestamp=None):
    if not token:
        raise HTTPException(401, "invalid_auth")
    try:
        pairs = parse_qsl(raw, keep_blank_values=True, strict_parsing=True)
        data = dict(pairs)
        if len(data) != len(pairs):
            raise ValueError("Duplicate fields")
        received = data.pop("hash")
        secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
        check = "\n".join(f"{key}={value}" for key, value in sorted(data.items()))
        expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        age = (timestamp or int(time.time())) - int(data["auth_date"])
        if not hmac.compare_digest(expected, received) or age < -30 or age > max_age:
            raise ValueError("Invalid signature or expired data")
        user = json.loads(data["user"])
        if not isinstance(user["id"], int) or user["id"] <= 0:
            raise ValueError("Invalid identity")
        return user
    except (ValueError, KeyError, TypeError) as error:
        raise HTTPException(401, "invalid_auth") from error


async def resolve_user(db, identity):
    if db.bind.dialect.name == "postgresql":
        await db.execute(text("SELECT pg_advisory_xact_lock(:identity)"), {"identity": -int(identity["id"])})
    user = await db.get(User, identity["id"])
    if not user:
        user = User(
            id=identity["id"],
            name=identity.get("first_name", "Telegram"),
            language=detect_language(identity.get("language_code")),
        )
        db.add(user)
    else:
        user.name = identity.get("first_name", user.name)
    await db.flush()
    return user


async def exchange(db, raw):
    identity = verify_init_data(raw, settings().bot_token, settings().auth_max_age)
    digest = hashlib.sha256(raw.encode()).hexdigest()
    # One exchange per signed launch; reloads reuse the session token stored by the client.
    if not await redis.set(f"launch:{digest}", "1", ex=settings().auth_max_age, nx=True):
        raise HTTPException(401, "invalid_auth")
    user = await resolve_user(db, identity)
    await db.commit()
    token = secrets.token_urlsafe(32)
    await redis.set(f"session:{token}", str(user.id), ex=86400)
    return token, user


async def current_user(request: Request, authorization: str = Header(default=""), db: AsyncSession = Depends(session)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "invalid_auth")
    token = authorization[7:]
    identifier = await redis.get(f"session:{token}")
    if not identifier:
        raise HTTPException(401, "invalid_auth")
    user = await db.get(User, int(identifier))
    if not user:
        raise HTTPException(401, "invalid_auth")
    request.state.language = user.language
    return user


async def administrator(user: User = Depends(current_user)):
    if user.id not in settings().admins:
        raise HTTPException(403, "forbidden")
    return user
