@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo   建筑规范图集智能体 一键启动
echo ============================================

if not exist ".venv\Scripts\python.exe" (
    echo [1/4] 正在创建 Python 虚拟环境...
    py -3.12 -m venv .venv
)

echo [2/4] 正在检查并安装依赖...
".venv\Scripts\python.exe" -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --disable-pip-version-check

echo [3/4] 正在启动接口服务 http://localhost:8000 ...
start "建筑规范智能体-API" cmd /k ".venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000"

echo [4/4] 正在启动网页服务 http://localhost:8501 ...
start "建筑规范智能体-Web" cmd /k ".venv\Scripts\streamlit run app.py --server.port 8501"

echo.
echo 启动完成，请打开浏览器访问 http://localhost:8501
echo 关闭对应黑色窗口即可停止服务。
timeout /t 5 >nul
