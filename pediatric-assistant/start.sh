#!/bin/bash
# 快速启动前后端

BACKEND_DIR="/Users/zhang/Desktop/Claude/pediatric-assistant/backend"
FRONTEND_DIR="/Users/zhang/Desktop/Claude/pediatric-assistant/frontend"

# 后端
cd "$BACKEND_DIR" && source venv/bin/activate && nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &

# 前端
cd "$FRONTEND_DIR" && nohup python3 -m http.server 8002 --bind 0.0.0.0:8002 &

echo "✓ 后端: http://localhost:8000"
echo "✓ 前端: http://localhost:8002"
