#!/bin/bash

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="/Users/wuchenkai/深度学习模型"

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 清理函数 - 仅在用户主动 Ctrl+C 时触发
cleanup() {
    log_info "正在清理进程..."
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null || true
    fi
    # 注意：不杀死后端进程，让其继续运行
    log_info "前端服务已停止，后端服务继续运行"
}

# 设置退出陷阱 - 仅响应 INT (Ctrl+C)
trap cleanup INT

# 启用 set -e 用于前期检查
set -e

# 检查虚拟环境
log_info "检查 Python 虚拟环境..."
if [ ! -d "$PROJECT_ROOT/venv" ]; then
    log_error "虚拟环境不存在，请先运行: python setup_env.py"
    exit 1
fi
log_success "虚拟环境检查通过"

# 检查前端依赖
log_info "检查前端依赖..."
if [ ! -d "$PROJECT_ROOT/frontend/node_modules" ]; then
    log_warning "前端依赖未安装，正在安装..."
    cd "$PROJECT_ROOT/frontend"
    npm install
    log_success "前端依赖安装完成"
else
    log_success "前端依赖检查通过"
fi

# 激活虚拟环境
log_info "激活 Python 虚拟环境..."
cd "$PROJECT_ROOT"
source venv/bin/activate
log_success "虚拟环境已激活"

# 创建存储目录
log_info "初始化存储目录..."
python3 << 'EOF'
from backend.config.settings import ensure_directories
ensure_directories()
print("✅ 存储目录初始化完成")
EOF

# 可选：运行验证脚本
if [ "$1" == "--verify" ]; then
    log_info "运行架构验证..."
    python verify_implementation.py
    if [ $? -ne 0 ]; then
        log_error "验证失败，请检查上述错误"
        exit 1
    fi
fi

# 启动后端服务
log_info "启动后端服务..."
log_info "后端地址: http://localhost:8000"
log_info "API 文档: http://localhost:8000/docs"
uvicorn backend.api.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --timeout-keep-alive 43200 &
BACKEND_PID=$!
log_success "后端服务已启动 (PID: $BACKEND_PID)"

# 等待后端启动
sleep 2

# 检查后端是否成功启动
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    log_error "后端启动失败"
    exit 1
fi

# 关闭 set -e，防止后续命令失败导致脚本退出
# 这确保了即使前端启动失败，后端服务也会继续运行
set +e

# 启动前端服务
log_info "启动前端服务..."
cd "$PROJECT_ROOT/frontend"
npm run dev &
FRONTEND_PID=$!
log_success "前端服务已启动 (PID: $FRONTEND_PID)"

# 等待前端启动
sleep 3

# 检查前端是否成功启动（非致命错误）
if ! kill -0 $FRONTEND_PID 2>/dev/null; then
    log_warning "前端启动失败，但后端服务继续运行"
    FRONTEND_PID=""
fi

# 显示启动信息
echo ""
log_success "后端服务已启动并运行中！"
if [ ! -z "$FRONTEND_PID" ]; then
    log_success "前端服务已启动！"
fi
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  遥感影像病害木检测系统${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${BLUE}前端地址:${NC}     http://localhost:5173"
echo -e "  ${BLUE}后端地址:${NC}     http://localhost:8000"
echo -e "  ${BLUE}API 文档:${NC}     http://localhost:8000/docs"
echo -e "  ${BLUE}健康检查:${NC}     http://localhost:8000/health"
echo ""
echo -e "  ${BLUE}后端进程:${NC}     $BACKEND_PID (持续运行)"
if [ ! -z "$FRONTEND_PID" ]; then
    echo -e "  ${BLUE}前端进程:${NC}     $FRONTEND_PID"
fi
echo ""
echo -e "  ${YELLOW}按 Ctrl+C 停止前端服务（后端继续运行）${NC}"
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo ""

# 等待前端进程（如果存在）
# 后端进程独立运行，不受脚本控制
if [ ! -z "$FRONTEND_PID" ]; then
    wait $FRONTEND_PID
else
    # 如果前端未启动，保持脚本运行以保持后端进程活跃
    while true; do
        sleep 3600
    done
fi
