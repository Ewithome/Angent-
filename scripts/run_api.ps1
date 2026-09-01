# 启动企业级 FastAPI 接口服务，文档地址 http://localhost:8000/docs
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path ".venv")) {
    Write-Host "请先执行: python -m venv .venv && .venv\Scripts\Activate.ps1 && pip install -r requirements.txt"
    exit 1
}

& .venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
