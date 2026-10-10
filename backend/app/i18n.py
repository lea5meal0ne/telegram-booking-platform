from datetime import datetime
from zoneinfo import ZoneInfo

TEXT = {
    "deletion": (
        "Запрос на удаление персональных данных: {name} (Telegram ID: {user_id}). Обработайте запрос с учётом обязательных сроков хранения.",
        "Personal data deletion request: {name} (Telegram ID: {user_id}). Process the request subject to required retention periods.",
    ),
    "unavailable": (
        "Сервис временно недоступен. Попробуйте позже.",
        "Service temporarily unavailable. Try again later.",
    ),
    "welcome": ("Добро пожаловать! Выберите раздел.", "Welcome! Choose a section."),
    "help": (
        "Выберите услугу, дату и время в приложении. Управляйте записями в разделе «Мои записи». /support — помощь, /language — язык.",
        "Choose a service, date and time in the app. Manage bookings in My appointments. /support — help, /language — language.",
    ),
    "book": ("📅 Записаться", "📅 Book"),
    "appointments": ("📋 Мои записи", "📋 My appointments"),
    "portfolio": ("🖼 Портфолио", "🖼 Portfolio"),
    "reviews": ("⭐ Отзывы", "⭐ Reviews"),
    "contacts": ("📞 Контакты", "📞 Contacts"),
    "support": ("💬 Поддержка", "💬 Support"),
    "profile": ("⚙️ Личный кабинет", "⚙️ Profile"),
    "admin": ("⚙️ Администратор", "⚙️ Administrator"),
    "language": ("🌐 Язык", "🌐 Language"),
    "saved": ("Сохранено.", "Saved."),
    "forbidden": ("Доступ запрещён.", "Access denied."),
    "not_found": ("Не найдено.", "Not found."),
    "invalid_auth": ("Откройте приложение через Telegram.", "Open the app through Telegram."),
    "conflict": ("Время уже занято. Выберите другое.", "This time is unavailable. Choose another."),
    "invalid": ("Проверьте введённые данные.", "Check the entered data."),
    "cancellation_closed": (
        "Срок изменения записи истёк. Обратитесь в поддержку.",
        "The change deadline has passed. Contact support.",
    ),
    "review_ineligible": (
        "Отзыв доступен только после подтверждённого посещения.",
        "A review requires a verified visit.",
    ),
    "duplicate": ("Действие уже выполнено.", "This action has already been completed."),
    "rate_limit": ("Слишком много запросов. Попробуйте позже.", "Too many requests. Try again later."),
    "confirm": ("✅ Подтверждаю", "✅ Confirm"),
    "cancel": ("❌ Отменить", "❌ Cancel"),
    "attended": ("✅ Клиент пришёл", "✅ Attended"),
    "no_show": ("❌ Клиент не пришёл", "❌ No show"),
    "later": ("⏳ Отметить позже", "⏳ Decide later"),
    "booking": (
        "📅 Запись создана: {service}\n{date}\n{address}",
        "📅 Appointment booked: {service}\n{date}\n{address}",
    ),
    "reminder": (
        "📅 Напоминание: {service}\n{date}\n{address}\nПожалуйста, подтвердите запись.",
        "📅 Reminder: {service}\n{date}\n{address}\nPlease confirm your appointment.",
    ),
    "attendance": (
        "Посещение завершилось: {service}\n{date}\nПодтвердите посещение клиента.",
        "Appointment ended: {service}\n{date}\nVerify the customer’s attendance.",
    ),
    "review": ("⭐ Спасибо за визит! Оставьте отзыв.", "⭐ Thank you for visiting! Leave a review."),
    "changed": ("Запись изменена: {service}\n{date}", "Appointment updated: {service}\n{date}"),
    "canceled": ("Запись отменена: {service}\n{date}", "Appointment canceled: {service}\n{date}"),
    "customer": ("Клиент: {name}\n", "Customer: {name}\n"),
    "support_prompt": (
        "Отправьте сообщение или фото. Ответ придёт сюда. /cancel — выйти из поддержки.",
        "Send a message or photo. Replies will arrive here. /cancel — exit support.",
    ),
    "support_received": ("Сообщение отправлено.", "Message sent."),
    "support_message": ("💬 Поддержка #{conversation}:\n{text}", "💬 Support #{conversation}:\n{text}"),
    "support_reply": ("💬 Ответ поддержки:\n{text}", "💬 Support reply:\n{text}"),
    "reply_help": (
        "Ответьте на это сообщение, чтобы написать клиенту.",
        "Reply to this message to contact the customer.",
    ),
    "confirmation": (
        "Подтверждение клиента: {customer}\nПодтверждение администратора: {admin}",
        "Customer confirmation: {customer}\nAdministrator confirmation: {admin}",
    ),
    "yes": ("да", "yes"),
    "pending": ("ожидается", "pending"),
}


def detect_language(code: str | None):
    return "ru" if not code or code.lower().startswith("ru") else "en"


def tr(key: str, language="ru", **values):
    pair = TEXT.get(key, TEXT["invalid"])
    return pair[1 if language == "en" else 0].format(**values)


def content(value, language="ru"):
    return value.get(language) or value.get("ru") or "" if isinstance(value, dict) else value


def format_date(value: datetime, timezone: str):
    return value.astimezone(ZoneInfo(timezone)).strftime("%d.%m.%Y %H:%M")
