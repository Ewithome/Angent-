"""智能体对话接口。"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Request

from api.schemas import ApiResponse, ChatData, ChatRequest
from api.services.agent_service import run_chat

router = APIRouter(prefix="/chat", tags=["对话"])


@router.post("", response_model=ApiResponse[ChatData], summary="发送消息给智能体")
async def chat(request: Request, body: ChatRequest) -> ApiResponse[ChatData]:
    session_id = body.session_id or "default"
    try:
        # 同步 LLM 调用放到线程池执行，避免阻塞 FastAPI 事件循环
        reply = await asyncio.to_thread(
            run_chat,
            body.message,
            session_id,
            body.engine,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"智能体调用失败: {exc}") from exc
    data = ChatData(session_id=session_id, reply=reply)
    return ApiResponse[ChatData](data=data, request_id=request.state.request_id)
