"""MCP 服务配置接口：新增、修改、删除与重新加载。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from api.schemas import ApiResponse
from harness.mcp_config import BUILTIN_SERVER_NAME, McpServerConfig, get_mcp_store

router = APIRouter(prefix="/mcp/servers", tags=["MCP"])


def _reload_harness() -> None:
    """配置变更后通知当前进程内的 Harness 网关，下次对话自动重启生效。"""
    try:
        from harness.agent import get_gateway

        get_gateway().reload_mcp_servers()
    except Exception:  # noqa: BLE001
        # 网关未启动或 SDK 不可用时不影响配置保存
        pass


@router.get(
    "",
    response_model=ApiResponse[list[McpServerConfig]],
    summary="获取 MCP 服务列表",
)
def list_mcp_servers(request: Request) -> ApiResponse[list[McpServerConfig]]:
    try:
        servers = get_mcp_store().list_all()
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse[list[McpServerConfig]](
        data=servers,
        request_id=request.state.request_id,
    )


@router.post(
    "",
    response_model=ApiResponse[McpServerConfig],
    summary="新增 MCP 服务",
)
def create_mcp_server(
    request: Request,
    body: McpServerConfig,
) -> ApiResponse[McpServerConfig]:
    store = get_mcp_store()
    if body.name == BUILTIN_SERVER_NAME:
        raise HTTPException(status_code=400, detail="该名称是内置 MCP 服务，不能创建")
    if store.get_custom(body.name) is not None:
        raise HTTPException(status_code=409, detail=f"MCP 服务已存在：{body.name}")
    try:
        saved = store.upsert(body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _reload_harness()
    return ApiResponse[McpServerConfig](
        data=saved,
        message="MCP 服务已新增",
        request_id=request.state.request_id,
    )


@router.put(
    "/{name}",
    response_model=ApiResponse[McpServerConfig],
    summary="修改 MCP 服务",
)
def update_mcp_server(
    name: str,
    request: Request,
    body: McpServerConfig,
) -> ApiResponse[McpServerConfig]:
    store = get_mcp_store()
    if name == BUILTIN_SERVER_NAME:
        raise HTTPException(status_code=400, detail="内置 MCP 服务不能修改")
    if store.get_custom(name) is None:
        raise HTTPException(status_code=404, detail=f"MCP 服务不存在：{name}")
    if body.name != name:
        raise HTTPException(status_code=422, detail="路径名称与请求体名称不一致")
    try:
        saved = store.upsert(body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _reload_harness()
    return ApiResponse[McpServerConfig](
        data=saved,
        message="MCP 服务已更新",
        request_id=request.state.request_id,
    )


@router.delete(
    "/{name}",
    response_model=ApiResponse[dict],
    summary="删除 MCP 服务",
)
def delete_mcp_server(
    name: str,
    request: Request,
) -> ApiResponse[dict]:
    store = get_mcp_store()
    if name == BUILTIN_SERVER_NAME:
        raise HTTPException(status_code=400, detail="内置 MCP 服务不能删除")
    if not store.delete(name):
        raise HTTPException(status_code=404, detail=f"MCP 服务不存在：{name}")
    _reload_harness()
    return ApiResponse[dict](
        data={"name": name, "deleted": True},
        message="MCP 服务已删除",
        request_id=request.state.request_id,
    )


@router.post(
    "/reload",
    response_model=ApiResponse[dict],
    summary="重新加载 MCP 服务配置",
)
def reload_mcp_servers(request: Request) -> ApiResponse[dict]:
    _reload_harness()
    return ApiResponse[dict](
        data={"reloaded": True},
        message="MCP 配置将在下次 Agent Harness 对话时生效",
        request_id=request.state.request_id,
    )
