@echo off
REM 智能儿科分诊与护理助手 - Windows启动脚本

echo ======================================
echo   智能儿科分诊与护理助手
echo ======================================
echo.

REM 检查Python环境
python --version >nul 2>&1
if errorlevel 1 (
    echo [X] 未找到 Python，请先安装
    pause
    exit /b 1
)

echo [OK] Python 已安装
echo.

REM 进入后端目录
cd backend

REM 检查依赖
echo [.] 检查后端依赖...
python -c "import fastapi" >nul 2>&1
if errorlevel 1 (
    echo [.] 正在安装依赖...
    pip install -r requirements.txt
)

echo.
echo ======================================
echo   启动选项
echo ======================================
echo 1. 启动后端服务
echo 2. 运行评估测试
echo 3. 检查系统状态
echo 4. 退出
echo.

set /p choice=请选择 [1-4]:

if "%choice%"=="1" (
    echo.
    echo [OK] 启动后端服务...
    echo 服务地址: http://localhost:8000
    echo API文档: http://localhost:8000/docs
    echo.
    echo 按 Ctrl+C 停止服务
    echo.
    python app/main.py
) else if "%choice%"=="2" (
    echo.
    echo [OK] 运行评估测试...
    echo.
    python evaluation/run_evaluation.py --test-file app/data/test_cases.json --output-file evaluation_report.json
    pause
) else if "%choice%"=="3" (
    echo.
    echo [OK] 检查系统状态...
    echo.
    echo Python 模块:
    python -c "import fastapi" && echo   [OK] fastapi || echo   [X] fastapi
    python -c "import uvicorn" && echo   [OK] uvicorn || echo   [X] uvicorn
    python -c "import openai" && echo   [OK] openai || echo   [X] openai
    echo.
    pause
) else if "%choice%"=="4" (
    exit /b 0
) else (
    echo [X] 无效选择
    pause
    exit /b 1
)
