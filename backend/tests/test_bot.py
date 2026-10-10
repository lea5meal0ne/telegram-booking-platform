from types import SimpleNamespace
from unittest.mock import AsyncMock
from sqlalchemy import select
from app.bot import commands, switch_language, support_command, support_message
from app.auth import redis
from app.models import Job
from app import services as logic
from app.db import Session
from app.schemas import MessageInput


def sender(identifier=100, language="en"):
    return SimpleNamespace(id=identifier, first_name="Customer", language_code=language)


async def test_bot_respects_persisted_language(db, seed):
    seed[0].language = "ru"
    seed[0].explicit_language = True
    await db.commit()
    message = SimpleNamespace(text="/start", from_user=sender(), answer=AsyncMock())
    await commands(message)
    assert "Добро пожаловать" in message.answer.call_args.args[0]


async def test_bot_language_synchronizes_with_database(db, seed):
    callback = SimpleNamespace(
        data="lang:ru", from_user=sender(), message=SimpleNamespace(answer=AsyncMock()), answer=AsyncMock()
    )
    await switch_language(callback)
    await db.refresh(seed[0])
    assert seed[0].language == "ru" and seed[0].explicit_language


async def test_bot_blocks_admin_command_for_customer(db, seed):
    message = SimpleNamespace(text="/admin", from_user=sender(), answer=AsyncMock())
    await commands(message)
    assert message.answer.call_args.args[0] == "Access denied."


async def test_bot_support_routes_to_administrator(db, seed):
    message = SimpleNamespace(from_user=sender(), answer=AsyncMock())
    await support_command(message)
    assert await redis.get("support-mode:100")
    incoming = SimpleNamespace(
        from_user=sender(), text="Help from bot", caption=None, photo=None, reply_to_message=None, answer=AsyncMock()
    )
    await support_message(incoming)
    assert await db.scalar(select(Job.id).where(Job.recipient_id == 900, Job.kind == "support_message"))


async def test_bot_admin_reply_routes_to_original_customer(db, seed):
    conversation = await logic.conversation_for(db, seed[0])
    await db.commit()
    await logic.send_support(db, seed[0], conversation.id, MessageInput(text="Help"))
    message = SimpleNamespace(
        from_user=sender(900, "ru"),
        text="Private reply",
        caption=None,
        photo=None,
        reply_to_message=SimpleNamespace(text=f"💬 Support #{conversation.id}:\nHelp", caption=None),
        answer=AsyncMock(),
    )
    await support_message(message)
    async with Session() as check:
        assert await check.scalar(select(Job.id).where(Job.recipient_id == 100, Job.kind == "support_reply"))
