"""技能管理接口：查询、新增、编辑与删除本地 SKILL.md。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from api.schemas import ApiResponse
from harness.skills_store import SkillInfo, delete_skill, list_skills, upsert_skill

router = APIRouter(prefix="/skills", tags=["Skills"])


class SkillRequest(BaseModel):
    """网页或外部系统提交的技能内容。"""

    name: str = Field(..., description="kebab-case 技能名称")
    description: str = Field(..., min_length=1, max_length=500, description="用途说明")
    when_to_use: str = Field(default="", max_length=500, description="可选路由提示")
    content: str = Field(..., min_length=1, description="完整 Markdown 指令正文")


@router.get(
    "",
    response_model=ApiResponse[list[SkillInfo]],
    summary="获取技能列表",
)
def get_skills(request: Request) -> ApiResponse[list[SkillInfo]]:
    return ApiResponse[list[SkillInfo]](
        data=list_skills(),
        request_id=request.state.request_id,
    )


@router.post(
    "",
    response_model=ApiResponse[SkillInfo],
    summary="新增技能",
)
def create_skill(
    request: Request,
    body: SkillRequest,
) -> ApiResponse[SkillInfo]:
    try:
        saved = upsert_skill(
            name=body.name,
            description=body.description,
            when_to_use=body.when_to_use,
            content=body.content,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiResponse[SkillInfo](
        data=saved,
        message="技能已新增",
        request_id=request.state.request_id,
    )


@router.put(
    "/{name}",
    response_model=ApiResponse[SkillInfo],
    summary="更新技能",
)
def update_skill(
    name: str,
    request: Request,
    body: SkillRequest,
) -> ApiResponse[SkillInfo]:
    if body.name != name:
        raise HTTPException(status_code=422, detail="路径名称与请求体名称不一致")
    try:
        saved = upsert_skill(
            name=body.name,
            description=body.description,
            when_to_use=body.when_to_use,
            content=body.content,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiResponse[SkillInfo](
        data=saved,
        message="技能已更新",
        request_id=request.state.request_id,
    )


@router.delete(
    "/{name}",
    response_model=ApiResponse[dict],
    summary="删除技能",
)
def remove_skill(
    name: str,
    request: Request,
) -> ApiResponse[dict]:
    try:
        deleted = delete_skill(name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail=f"技能不存在或为只读示例：{name}")
    return ApiResponse[dict](
        data={"name": name, "deleted": True},
        message="技能已删除",
        request_id=request.state.request_id,
    )
