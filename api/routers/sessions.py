"""会话管理接口。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from api.schemas import ApiResponse, SessionData
from api.services.agent_service import delete_session, list_session_messages

router = APIRouter(prefix="/sessions", tags=["会话"])


@router.get(
    "/{session_id}/messages",
    response_model=ApiResponse[SessionData],
    summary="获取会话消息",
)
def get_session_messages(
    session_id: str,
    request: Request,
    limit: int = Query(default=50, ge=1, le=200, description="返回最近 N 条消息"),
) -> ApiResponse[SessionData]:
    messages = list_session_messages(session_id, limit)
    data = SessionData(session_id=session_id, messages=messages)
    return ApiResponse[SessionData](data=data, request_id=request.state.request_id)


@router.delete(
    "/{session_id}",
    response_model=ApiResponse[None],
    summary="删除会话",
)
def remove_session(
    session_id: str,
    request: Request,
) -> ApiResponse[None]:
    try:
        delete_session(session_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"删除会话失败: {exc}") from exc
    return ApiResponse[None](
        message="会话已删除",
        request_id=request.state.request_id,
    )
