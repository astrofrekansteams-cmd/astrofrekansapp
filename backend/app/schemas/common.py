from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class APIModel(BaseModel):
    """Base for every request/response model."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ErrorDetail(APIModel):
    code: str = Field(examples=["validation_error"])
    message: str = Field(examples=["The submitted data is not valid."])
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(APIModel):
    """The only error shape the API ever returns."""

    error: ErrorDetail


class Page(APIModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class Message(APIModel):
    message: str
