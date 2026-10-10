import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, FSInputFile
from sqlalchemy import select
from app.config import settings
from app.db import Session
from app.models import Job, Appointment, User
from app.services import business, utc, UTC, booking_lock
from app.i18n import tr, content, format_date
from app.logging import configure_logging

log = logging.getLogger(__name__)


def buttons(kind, identifier, language):
    rows = []
    if kind == "reminder":
        rows.append(
            [
                InlineKeyboardButton(text=tr("confirm", language), callback_data=f"confirm:{identifier}"),
                InlineKeyboardButton(text=tr("cancel", language), callback_data=f"cancel:{identifier}"),
            ]
        )
    if kind == "attendance":
        rows.append(
            [
                InlineKeyboardButton(text=tr(key, language), callback_data=f"{key}:{identifier}")
                for key in ("attended", "no_show")
            ]
        )
        rows.append([InlineKeyboardButton(text=tr("later", language), callback_data=f"later:{identifier}")])
    path = (
        f"reviews?appointment={identifier}"
        if kind == "review"
        else "support"
        if kind.startswith("support")
        else "appointments"
    )
    rows.append(
        [
            InlineKeyboardButton(
                text=tr(
                    "reviews" if kind == "review" else "support" if kind.startswith("support") else "appointments",
                    language,
                ),
                web_app=WebAppInfo(url=f"{settings().mini_app_url}/{path}"),
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def deliver(bot, db, job):
    user = await db.get(User, job.recipient_id)
    language = user.language if user else "ru"
    config = (await business(db)).data
    values = dict(job.payload)
    appointment = await db.get(Appointment, job.appointment_id) if job.appointment_id else None
    if job.appointment_id and not appointment:
        return
    if appointment:
        if job.kind in {"booking", "reminder", "attendance", "changed"} and appointment.status != "booked":
            return
        customer = await db.get(User, appointment.user_id)
        values.update(
            service=content(appointment.snapshot["name"], language),
            date=format_date(utc(appointment.start), config["timezone"]),
            address=config.get("address", ""),
        )
        body = tr(job.kind, language, **values)
        if job.recipient_id in settings().admins:
            body = tr("customer", language, name=customer.name) + body
            if job.kind == "reminder":
                body += "\n" + tr(
                    "confirmation",
                    language,
                    customer=tr("yes" if appointment.customer_confirmed else "pending", language),
                    admin=tr("yes" if appointment.admin_confirmed else "pending", language),
                )
    else:
        body = tr(job.kind, language, **values)
        if job.kind == "support_message":
            body += "\n" + tr("reply_help", language)
    markup = buttons(job.kind, job.appointment_id or 0, language)
    image = values.get("image")
    if image:
        path = Path(settings().uploads_dir) / image.rsplit("/", 1)[-1]
        await bot.send_photo(job.recipient_id, FSInputFile(path), caption=body[:1024], reply_markup=markup)
        if len(body) > 1024:
            await bot.send_message(job.recipient_id, body[1024:])
    else:
        await bot.send_message(job.recipient_id, body, reply_markup=markup)


async def process_one(bot, clock=None):
    # Hold a row lock during delivery. A crash releases it; pending jobs recover on restart.
    # Telegram has no idempotency key: a crash after sending can cause a duplicate delivery.
    async with Session() as db:
        await booking_lock(db)
        job = await db.scalar(
            select(Job)
            .where(Job.state == "pending", Job.due <= (clock or datetime.now(UTC)))
            .order_by(Job.due)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if not job:
            return False
        try:
            await deliver(bot, db, job)
            job.state = "sent"
        except Exception:
            job.attempts += 1
            job.due = datetime.now(UTC) + timedelta(seconds=min(3600, 30 * 2 ** min(job.attempts, 7)))
            if job.attempts >= 10:
                job.state = "failed"
            log.warning("Notification delivery failed job=%s attempt=%s", job.id, job.attempts)
        await db.commit()
        return True


async def main():
    configure_logging()
    async with Bot(settings().bot_token) as bot:
        while True:
            if not await process_one(bot):
                await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(main())
