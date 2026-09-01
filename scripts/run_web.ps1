# 启动 Streamlit 中文聊天界面，地址 http://localhost:8501
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path ".venv")) {
    Write-Host "请先执行: python -m venv .venv && .venv\Scripts\Activate.ps1 && pip install -r requirements.txt"
    exit 1
}

& .venv\Scripts\streamlit.exe run app.py --server.port 8501
