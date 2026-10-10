from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from urllib.parse import urlsplit
import re


class Localized(BaseModel):
    ru: str = Field(min_length=1, max_length=200)
    en: str = Field(default="", max_length=200)


class ServiceInput(BaseModel):
    name: Localized
    description: dict[str, str] = Field(default_factory=dict)
    price: int = Field(ge=0, le=1000000000)
    currency: str = Field(default="RUB", pattern=r"^[A-Z]{3}$")
    duration: int = Field(ge=5, le=1440)
    image: str = Field(default="", max_length=500)
    active: bool = True
    position: int = Field(default=0, ge=0)

    @field_validator("image")
    @classmethod
    def image_url(cls, value):
        if value and not re.fullmatch(r"/api/media/[a-f0-9]{32}\.jpg", value):
            raise ValueError("Invalid media")
        return value


class BookingInput(BaseModel):
    service_id: int
    start: datetime
    request_key: str = Field(min_length=16, max_length=100)

    @field_validator("start")
    @classmethod
    def aware(cls, value):
        if value.tzinfo is None:
            raise ValueError("Timezone required")
        return value


class MoveInput(BaseModel):
    start: datetime

    @field_validator("start")
    @classmethod
    def aware(cls, value):
        return BookingInput.aware(value)


class ScheduleInput(BaseModel):
    weekday: int | None = Field(default=None, ge=0, le=6)
    date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    start: str = Field(default="09:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    end: str = Field(default="18:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    blocked: bool = False

    @model_validator(mode="after")
    def valid(self):
        if (self.weekday is None) == (self.date is None) or self.end <= self.start:
            raise ValueError("Specify exactly one weekday or date and a valid interval")
        if self.date:
            from datetime import date

            date.fromisoformat(self.date)
        return self


class ReviewInput(BaseModel):
    appointment_id: int
    rating: int = Field(ge=1, le=5)
    text: str = Field(default="", max_length=4000)
    anonymous: bool = False


class MessageInput(BaseModel):
    text: str = Field(default="", max_length=4000)
    image: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def valid(self):
        if not self.text.strip() and not self.image:
            raise ValueError("Empty message")
        if self.image and not re.fullmatch(r"/api/media/[a-f0-9]{32}\.jpg", self.image):
            raise ValueError("Invalid image")
        return self


class PortfolioInput(BaseModel):
    category_id: int | None = None
    description: dict[str, str] = Field(default_factory=dict)
    images: list[str] = Field(default_factory=list, max_length=30)
    position: int = Field(default=0, ge=0)

    @field_validator("images")
    @classmethod
    def valid_images(cls, values):
        if any(not re.fullmatch(r"/api/media/[a-f0-9]{32}\.jpg", x) for x in values):
            raise ValueError("Only uploaded images are allowed")
        return values


class BusinessInput(BaseModel):
    name: Localized
    description: dict[str, str] = Field(default_factory=dict)
    timezone: str = "Europe/Moscow"
    currency: str = Field(default="RUB", pattern=r"^[A-Z]{3}$")
    accent: str = Field(default="#5367db", pattern=r"^#[a-fA-F0-9]{6}$")
    address: str = Field(default="", max_length=1000)
    phone: str = Field(default="", max_length=100)
    telegram: str = Field(default="", max_length=100)
    website: str = Field(default="", max_length=500)
    social_links: list[str] = Field(default_factory=list, max_length=20)
    logo: str = ""
    cover: str = ""
    horizon_days: int = Field(default=60, ge=1, le=365)
    notice_minutes: int = Field(default=60, ge=0, le=43200)
    cancel_minutes: int = Field(default=120, ge=0, le=43200)
    slot_minutes: int = Field(default=30, ge=5, le=240)
    buffer_minutes: int = Field(default=0, ge=0, le=240)
    reminder_hours: int = Field(default=24, ge=1, le=168)

    @field_validator("timezone")
    @classmethod
    def tz(cls, value):
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as error:
            raise ValueError("Unknown timezone") from error
        return value

    @field_validator("website", "social_links")
    @classmethod
    def url(cls, value):
        values = value if isinstance(value, list) else [value]
        if any(
            x
            and (
                urlsplit(x).scheme != "https"
                or not urlsplit(x).hostname
                or urlsplit(x).username
                or urlsplit(x).password
            )
            for x in values
        ):
            raise ValueError("HTTPS URL required")
        return value

    @field_validator("logo", "cover")
    @classmethod
    def media(cls, value):
        if value and not re.fullmatch(r"/api/media/[a-f0-9]{32}\.jpg", value):
            raise ValueError("Invalid media")
        return value


# Explicit output contracts keep internal ORM state out of API responses.


class Output(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ServiceOutput(ServiceInput, Output):
    id: int


class ScheduleOutput(ScheduleInput, Output):
    id: int


class AppointmentOutput(Output):
    id: int
    user_id: int
    service_id: int
    start: datetime
    end: datetime
    status: Literal["booked", "canceled", "completed", "no_show"]
    snapshot: dict
    customer_confirmed: bool
    admin_confirmed: bool
    verified_by: int | None
    verified_at: datetime | None
    customer_name: str | None = None


class PortfolioOutput(PortfolioInput, Output):
    id: int


class CategoryOutput(Output):
    id: int
    name: dict[str, str]


class ConversationOutput(Output):
    id: int
    user_id: int
    status: Literal["open", "closed"]
    name: str | None = None


class MessageOutput(Output):
    id: int
    sender_id: int
    text: str
    image: str
    at: datetime
