"""API 请求与响应模型。"""
from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int = Field(default=0, description="业务状态码，0 表示成功")
    message: str = Field(default="success", description="提示信息")
    data: T | None = None
    request_id: str = Field(default="", description="请求追踪 ID")


class HealthData(BaseModel):
    status: str
    service: str
    version: str
    environment: str
    timestamp: str


class ChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="用户发给智能体的消息",
    )
    session_id: str | None = Field(
        default=None,
        max_length=128,
        description="会话 ID，缺省使用 default",
    )


class ChatData(BaseModel):
    session_id: str
    reply: str


class SessionMessage(BaseModel):
    role: str
    content: str


class SessionData(BaseModel):
    session_id: str
    messages: list[SessionMessage]
