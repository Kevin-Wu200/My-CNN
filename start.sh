#!/bin/bash

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
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

log_debug() {
    echo -e "${CYAN}[DEBUG]${NC} $1"
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

# 显示帮助信息
show_help() {
    echo ""
    echo -e "${BLUE}使用方法:${NC}"
    echo "  ./start.sh [选项]"
    echo ""
    echo -e "${BLUE}选项:${NC}"
    echo "  --verify              运行架构验证"
    echo "  --test                运行基础测试"
    echo "  --test-advanced       运行高级测试"
    echo "  --check-logs          检查日志验证"
    echo "  --help                显示此帮助信息"
    echo ""
    echo -e "${BLUE}示例:${NC}"
    echo "  ./start.sh                    # 启动服务"
    echo "  ./start.sh --verify           # 启动服务并验证"
    echo "  ./start.sh --test             # 运行基础测试"
    echo ""
}

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

# 处理命令行参数
case "$1" in
    --help)
        show_help
        exit 0
        ;;
    --verify)
        log_info "运行架构验证..."
        python verify_implementation.py
        if [ $? -ne 0 ]; then
            log_error "验证失败，请检查上述错误"
            exit 1
        fi
        ;;
    --test)
        log_info "运行基础测试..."
        python3 test_upload_implementation.py
        exit $?
        ;;
    --test-advanced)
        log_info "运行高级测试..."
        python3 test_advanced_scenarios.py
        exit $?
        ;;
    --check-logs)
        log_info "启动后端服务用于日志验证..."
        log_info "后端地址: http://localhost:8000"
        log_info "API 文档: http://localhost:8000/docs"
        uvicorn backend.api.main:app \
            --host 0.0.0.0 \
            --port 8000 \
            --timeout-keep-alive 43200
        exit $?
        ;;
esac

# 检查端口占用并清理
check_and_cleanup_port() {
    local port=$1
    log_info "检查端口 $port 是否被占用..."

    # 查找占用端口的进程
    local pid=$(lsof -ti:$port)

    if [ ! -z "$pid" ]; then
        log_warning "端口 $port 已被进程 $pid 占用"
        log_info "正在终止旧进程..."
        kill -9 $pid 2>/dev/null || true
        sleep 1

        # 再次检查
        pid=$(lsof -ti:$port)
        if [ ! -z "$pid" ]; then
            log_error "无法终止占用端口 $port 的进程 $pid"
            log_error "请手动执行: kill -9 $pid"
            exit 1
        fi
        log_success "端口 $port 已清理"
    else
        log_success "端口 $port 可用"
    fi
}

# 清理端口 8000
check_and_cleanup_port 8000

# 启动后端服务
log_info "启动后端服务..."
log_info "后端地址: http://localhost:8000"
log_info "API 文档: http://localhost:8000/docs"
log_debug "启动命令: uvicorn backend.api.main:app --host 0.0.0.0 --port 8000"
uvicorn backend.api.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --timeout-keep-alive 43200 &
BACKEND_PID=$!
log_success "后端服务已启动 (PID: $BACKEND_PID)"

# 等待后端启动
sleep 3

# 检查后端是否成功启动
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    log_error "后端启动失败"
    log_error "请检查日志: tail -f backend.log"
    exit 1
fi

log_success "后端服务健康检查通过"

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
echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║${NC}     遥感影像病害木检测系统 - 分片上传8步完整修复     ${BLUE}║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
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
echo -e "${CYAN}📚 文档和测试:${NC}"
echo -e "  ${CYAN}快速导航:${NC}     README_PROJECT_COMPLETION.md"
echo -e "  ${CYAN}技术文档:${NC}     IMPLEMENTATION_SUMMARY.md"
echo -e "  ${CYAN}测试报告:${NC}     COMPREHENSIVE_TEST_REPORT.md"
echo -e "  ${CYAN}中文总结:${NC}     FINAL_CHINESE_SUMMARY.md"
echo ""
echo -e "${CYAN}🧪 运行测试:${NC}"
echo -e "  ${CYAN}基础测试:${NC}     python3 test_upload_implementation.py"
echo -e "  ${CYAN}高级测试:${NC}     python3 test_advanced_scenarios.py"
echo ""
echo -e "${CYAN}📊 查看日志:${NC}"
echo -e "  ${CYAN}实时日志:${NC}     tail -f backend.log"
echo -e "  ${CYAN}特定标签:${NC}     grep 'CHUNK_RECEIVED' backend.log"
echo ""
echo -e "  ${YELLOW}按 Ctrl+C 停止前端服务（后端继续运行）${NC}"
echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║${NC}  ✅ 系统已准备好投入生产使用！                      ${BLUE}║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
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
