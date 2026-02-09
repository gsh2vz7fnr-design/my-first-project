@echo off
REM RAG数据管道环境设置脚本 (Windows)

setlocal

set SCRIPT_DIR=%~dp0
set PROJECT_ROOT=%SCRIPT_DIR%..

echo =========================================
echo RAG数据管道环境设置
echo =========================================
echo.

REM 检查Python
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到python命令
    pause
    exit /b 1
)

echo.
echo 使用方法：
echo.
echo   1. 创建并激活虚拟环境:
echo      python -m venv venv
echo      venv\Scripts\activate
echo.
echo   2. 安装依赖:
echo      pip install -r requirements.txt
echo.
echo   3. 运行测试预览:
echo      python scripts\test_ingest_preview.py
echo.
echo   4. 配置API密钥后运行完整脚本:
echo      python scripts\ingest_md_to_vector.py
echo.

pause
