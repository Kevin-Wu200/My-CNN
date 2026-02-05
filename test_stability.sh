#!/bin/bash

# 后端服务稳定性测试脚本
# 用于验证修改是否解决了 ECONNREFUSED 问题

set -e

PROJECT_ROOT="/Users/wuchenkai/深度学习模型"
BACKEND_URL="http://localhost:8000"
TEST_DURATION=120  # 测试持续时间（秒）

echo "=========================================="
echo "后端服务稳定性测试"
echo "=========================================="
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

# 检查后端是否运行
log_info "检查后端服务状态..."
if ! curl -s "$BACKEND_URL/health" > /dev/null 2>&1; then
    log_error "后端服务未运行，请先启动服务"
    exit 1
fi
log_success "后端服务已运行"

# 获取初始 PID
INITIAL_PID=$(lsof -i :8000 -t | head -1)
log_info "初始后端进程 PID: $INITIAL_PID"

# 测试循环
log_info "开始稳定性测试（持续 $TEST_DURATION 秒）..."
echo ""

HEALTH_CHECK_COUNT=0
HEALTH_CHECK_FAILURES=0
PID_CHANGES=0

START_TIME=$(date +%s)
END_TIME=$((START_TIME + TEST_DURATION))

while [ $(date +%s) -lt $END_TIME ]; do
    CURRENT_TIME=$(($(date +%s) - START_TIME))

    # 检查 PID 是否变化
    CURRENT_PID=$(lsof -i :8000 -t | head -1 2>/dev/null || echo "")
    if [ -z "$CURRENT_PID" ]; then
        log_error "[$CURRENT_TIME s] 后端进程已停止！"
        PID_CHANGES=$((PID_CHANGES + 1))
    elif [ "$CURRENT_PID" != "$INITIAL_PID" ]; then
        log_warning "[$CURRENT_TIME s] PID 变化: $INITIAL_PID → $CURRENT_PID"
        PID_CHANGES=$((PID_CHANGES + 1))
        INITIAL_PID=$CURRENT_PID
    fi

    # 检查健康状态
    if curl -s "$BACKEND_URL/health" > /dev/null 2>&1; then
        HEALTH_CHECK_COUNT=$((HEALTH_CHECK_COUNT + 1))
        echo -ne "\r✅ [$CURRENT_TIME s] 健康检查成功 (共 $HEALTH_CHECK_COUNT 次)"
    else
        HEALTH_CHECK_FAILURES=$((HEALTH_CHECK_FAILURES + 1))
        log_error "[$CURRENT_TIME s] 健康检查失败"
    fi

    sleep 2
done

echo ""
echo ""
echo "=========================================="
echo "测试结果"
echo "=========================================="
echo ""

log_info "总健康检查次数: $HEALTH_CHECK_COUNT"
log_info "健康检查失败次数: $HEALTH_CHECK_FAILURES"
log_info "PID 变化次数: $PID_CHANGES"

if [ $HEALTH_CHECK_FAILURES -eq 0 ] && [ $PID_CHANGES -eq 0 ]; then
    log_success "✅ 所有测试通过！后端服务稳定运行"
    exit 0
else
    log_error "❌ 测试失败，请检查上述错误"
    exit 1
fi
