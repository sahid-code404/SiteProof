import uuid

from pydantic import EmailStr, Field

from app.schemas.base import APIModel


class InspectorCreate(APIModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    employee_code: str | None = Field(default=None, max_length=80)
    phone: str | None = Field(default=None, max_length=40)


class InspectorResponse(APIModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    email: EmailStr
    employee_code: str | None = None
    phone: str | None = None
    active: bool


class InspectorPage(APIModel):
    items: list[InspectorResponse]
    page: int
    page_size: int
    total_items: int
    total_pages: int
