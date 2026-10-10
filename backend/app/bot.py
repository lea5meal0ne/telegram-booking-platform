import asyncio
import re
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, BotCommand
from fastapi import HTTPException
from app.auth import resolve_user, redis
from app.config import settings
from app.db import Session
from app.i18n import tr
from app.schemas import MessageInput
from app import services as logic
from app.logging import configure_logging

bot = None
dp = Dispatcher()
dp.message.filter(F.chat.type == "private")
dp.callback_query.filter(F.message.chat.type == "private")


async def identity(db, sender):
    return await resolve_user(
        db, {"id": sender.id, "first_name": sender.first_name, "language_code": sender.language_code}
    )


def menu(language, admin=False):
    keys = ["book", "appointments", "portfolio", "reviews", "contacts", "support", "profile"]
    paths = {"book": "book", "contacts": "profile", "profile": "profile"}
    if admin:
        keys.append("admin")
    rows = [
        [
            InlineKeyboardButton(
                text=tr(key, language), web_app=WebAppInfo(url=f"{settings().mini_app_url}/{paths.get(key, key)}")
            )
        ]
        for key in keys
    ]
    rows.append([InlineKeyboardButton(text=tr("language", language), callback_data="language")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@dp.message(Command("start", "help", "book", "appointments", "admin", "language", "cancel"))
async def commands(message: Message):
    async with Session() as db:
        user = await identity(db, message.from_user)
        command = message.text.split()[0].split("@")[0][1:]
        if command == "admin" and user.id not in settings().admins:
            await message.answer(tr("forbidden", user.language))
            return
        if command == "cancel":
            await redis.delete(f"support-mode:{user.id}")
        if command == "language":
            await message.answer(tr("language", user.language), reply_markup=language_keyboard())
        else:
            await message.answer(
                tr("help" if command == "help" else "welcome", user.language),
                reply_markup=menu(user.language, user.id in settings().admins),
            )
        await db.commit()


def language_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru"),
                InlineKeyboardButton(text="🇬🇧 English", callback_data="lang:en"),
            ]
        ]
    )


@dp.callback_query(F.data == "language")
async def languages(callback: CallbackQuery):
    await callback.message.answer(tr("language"), reply_markup=language_keyboard())
    await callback.answer()


@dp.callback_query(F.data.startswith("lang:"))
async def switch_language(callback: CallbackQuery):
    async with Session() as db:
        user = await identity(db, callback.from_user)
        user.language = callback.data.split(":")[1]
        user.explicit_language = True
        await db.commit()
        await callback.message.answer(
            tr("saved", user.language), reply_markup=menu(user.language, user.id in settings().admins)
        )
        await callback.answer()


@dp.callback_query(F.data.regexp(r"^(confirm|cancel|attended|no_show|later):\d+$"))
async def appointment_callback(callback: CallbackQuery):
    async with Session() as db:
        user = await identity(db, callback.from_user)
        action, identifier = callback.data.split(":")
        try:
            if action == "confirm":
                await logic.confirm(db, user, int(identifier))
            elif action == "cancel":
                await logic.cancel(db, user, int(identifier))
            else:
                await logic.attendance(db, user, int(identifier), action)
            await callback.answer(tr("saved", user.language))
        except HTTPException as error:
            await db.rollback()
            await callback.answer(tr(error.detail, user.language), show_alert=True)


@dp.message(Command("support"))
async def support_command(message: Message):
    async with Session() as db:
        user = await identity(db, message.from_user)
        conversation = await logic.conversation_for(db, user)
        await db.commit()
        await redis.set(f"support-mode:{user.id}", conversation.id, ex=86400)
        await message.answer(tr("support_prompt", user.language))


@dp.message(F.text | F.photo)
async def support_message(message: Message):
    async with Session() as db:
        user = await identity(db, message.from_user)
        conversation = await redis.get(f"support-mode:{user.id}")
        if user.id in settings().admins and message.reply_to_message:
            original = message.reply_to_message.text or message.reply_to_message.caption or ""
            match = re.search(r"#(\d+):", original)
            if match:
                conversation = match[1]
        if not conversation:
            await message.answer(
                tr("help", user.language), reply_markup=menu(user.language, user.id in settings().admins)
            )
            await db.commit()
            return
        image = ""
        if message.photo:
            from app.api import store_image
            import io

            if message.photo[-1].file_size and message.photo[-1].file_size > 8 * 1024 * 1024:
                await message.answer(tr("invalid", user.language))
                return
            buffer = io.BytesIO()
            await message.bot.download(message.photo[-1], destination=buffer)
            image = await store_image(buffer.getvalue())
        data = MessageInput(text=message.text or message.caption or "", image=image)
        try:
            await logic.send_support(db, user, int(conversation), data)
            await message.answer(tr("support_received", user.language))
        except HTTPException as error:
            await message.answer(tr(error.detail, user.language))


async def main():
    configure_logging()
    async with Bot(settings().bot_token) as client:
        for language in ("ru", "en"):
            keys = {
                "start": "welcome",
                "help": "help",
                "book": "book",
                "appointments": "appointments",
                "support": "support",
                "cancel": "cancel",
                "language": "language",
            }
            await client.set_my_commands(
                [BotCommand(command=command, description=tr(key, language)[:256]) for command, key in keys.items()],
                language_code=language,
            )
        await dp.start_polling(client)


if __name__ == "__main__":
    asyncio.run(main())
