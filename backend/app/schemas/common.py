from typing import Generic, TypeVar, Optional, Any
from pydantic import BaseModel

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    success: bool = True
    data: Optional[T] = None
    message: str = "OK"
    code: str = "SUCCESS"


class ErrorResponse(BaseModel):
    success: bool = False
    message: str
    code: str
    details: Optional[Any] = None


class PaginatedResponse(BaseModel, Generic[T]):
    success: bool = True
    data: list[T]
    total: int
    page: int
    page_size: int
    pages: int


# Alias used by routers that import a unified paginated wrapper
APIPaginatedResponse = PaginatedResponse

