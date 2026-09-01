"""FastAPI 应用入口：统一异常、请求追踪、CORS 与路由注册。"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.config import get_settings
from api.logging import setup_logging
from api.routers import chat, health, sessions
from api.schemas import ApiResponse

setup_logging()
logger = logging.getLogger("api")
settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="基于 LangChain v1 + DeepSeek 的企业级智能体 API",
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    request.state.request_id = request_id
    start = datetime.now()
    response = await call_next(request)
    duration_ms = (datetime.now() - start).total_seconds() * 1000
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "%s %s -> %s %.1fms",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = getattr(request.state, "request_id", "")
    content = ApiResponse(
        code=42200,
        message="请求参数校验失败",
        data={"errors": exc.errors()},
        request_id=request_id,
    ).model_dump()
    return JSONResponse(status_code=422, content=content)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    request_id = getattr(request.state, "request_id", "")
    content = ApiResponse(
        code=exc.status_code,
        message=str(exc.detail),
        request_id=request_id,
    ).model_dump()
    return JSONResponse(status_code=exc.status_code, content=content)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", "")
    logger.exception("未处理异常: %s", exc)
    content = ApiResponse(
        code=50000,
        message="服务器内部错误",
        request_id=request_id,
    ).model_dump()
    return JSONResponse(status_code=500, content=content)


app.include_router(health.router, prefix=settings.api_prefix)
app.include_router(chat.router, prefix=settings.api_prefix)
app.include_router(sessions.router, prefix=settings.api_prefix)


@app.get("/", tags=["系统"])
def root() -> ApiResponse[dict]:
    return ApiResponse[dict](
        data={
            "service": settings.app_name,
            "docs": "/docs",
            "api_prefix": settings.api_prefix,
        },
        request_id="",
    )
