```bash
#!/bin/bash

# 启动后端
echo "启动后端服务..."
cd /Users/wuchenkai/深度学习模型
source venv/bin/activate
uvicorn backend.api.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# 启动前端
echo "启动前端服务..."
cd /Users/wuchenkai/深度学习模型/frontend
npm run dev &
FRONTEND_PID=$!

echo "后端 PID: $BACKEND_PID"
echo "前端 PID: $FRONTEND_PID"
echo "按 Ctrl+C 停止所有服务"

# 等待中断信号
trap "kill $BACKEND_PID $FRONTEND_PID" EXIT
wait
```
