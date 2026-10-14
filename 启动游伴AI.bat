@echo off
chcp 65001 >nul
title 游伴 AI (YOUBAN AI) - AI 旅行潮玩平台
cd /d "%~dp0"

set YOUBAN_PORT=8770

echo ==================================================================
echo   游伴 AI . YOUBAN AI     带着它，去发现世界。
echo ==================================================================
echo.
echo   正在检查运行环境...
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo   [错误] 未找到 python，请先安装 Python 3.10 或更高版本。
    echo          下载地址: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo   Python 版本: %PYVER%
echo.

echo   检查依赖 (fastapi / uvicorn) ...
python -c "import fastapi, uvicorn" >nul 2>nul
if errorlevel 1 (
    echo   未安装依赖，正在自动安装...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo   [错误] 依赖安装失败，请手动执行:
        echo          python -m pip install -r requirements.txt
        echo.
        pause
        exit /b 1
    )
    echo   依赖安装完成。
) else (
    echo   依赖已就绪。
)

echo.
echo ==================================================================
echo   默认端口 %YOUBAN_PORT%（如需修改，请编辑本文件顶部的 YOUBAN_PORT）
echo ==================================================================
echo.
echo   启动后会自动打开浏览器。
echo   若 %YOUBAN_PORT% 被占用，启动器会自动改用其它端口，
echo   请以终端窗口中提示的地址为准。
echo.
echo   按 Ctrl+C 可停止服务。
echo.

start "" "http://127.0.0.1:%YOUBAN_PORT%/"
python run.py

echo.
echo   服务已停止。
pause
