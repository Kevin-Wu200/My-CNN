<template>
  <div class="task-progress-page">
    <Card class="progress-card">
      <div class="card-header">
        <h2>任务进度</h2>
        <p class="description">实时展示当前任务的执行进度和状态</p>
      </div>

      <!-- 无任务状态 -->
      <div v-if="!currentTask" class="empty-state">
        <div class="empty-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <circle cx="12" cy="12" r="10" />
            <path d="M12 6v6l4 2" />
          </svg>
        </div>
        <p class="empty-text">暂无运行中的任务</p>
        <p class="empty-hint">请在其他页面点击"开始检测"或"上传"按钮启动任务</p>
      </div>

      <!-- 任务运行中 -->
      <div v-else-if="currentTask.status === 'running'" class="task-running">
        <div class="task-header">
          <div class="task-info">
            <h3 class="task-title">{{ getTaskTypeLabel(currentTask.type) }}</h3>
            <p class="task-id">任务ID: {{ currentTask.id }}</p>
          </div>
          <div class="task-time">
            <p class="time-label">已运行时间</p>
            <p class="time-value">{{ elapsedTime }}</p>
          </div>
        </div>

        <div class="progress-section">
          <div class="progress-header">
            <span class="progress-label">{{ currentTask.currentStage || '处理中' }}</span>
            <span class="progress-percentage">{{ currentTask.progress }}%</span>
          </div>
          <div class="progress-bar-container">
            <div class="progress-bar" :style="{ width: currentTask.progress + '%' }"></div>
          </div>
        </div>

        <div class="task-details">
          <div class="detail-item">
            <span class="detail-label">任务类型</span>
            <span class="detail-value">{{ getTaskTypeLabel(currentTask.type) }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">当前进度</span>
            <span class="detail-value">{{ currentTask.progress }}%</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">创建时间</span>
            <span class="detail-value">{{ formatTime(currentTask.createdAt) }}</span>
          </div>
        </div>

        <div class="action-buttons">
          <Button
            variant="danger"
            @click="showStopConfirm = true"
            :disabled="isStopping"
          >
            {{ isStopping ? '终止中...' : '终止任务' }}
          </Button>
        </div>
      </div>

      <!-- 任务已完成 -->
      <div v-else-if="currentTask.status === 'completed'" class="task-completed">
        <div class="status-icon success">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <polyline points="20 6 9 17 4 12"></polyline>
          </svg>
        </div>
        <h3 class="status-title">任务已完成</h3>
        <p class="status-message">{{ getTaskTypeLabel(currentTask.type) }}任务已成功完成</p>

        <div class="task-details">
          <div class="detail-item">
            <span class="detail-label">任务类型</span>
            <span class="detail-value">{{ getTaskTypeLabel(currentTask.type) }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">完成进度</span>
            <span class="detail-value">{{ currentTask.progress }}%</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">创建时间</span>
            <span class="detail-value">{{ formatTime(currentTask.createdAt) }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">完成时间</span>
            <span class="detail-value">{{ formatTime(currentTask.lastUpdatedAt) }}</span>
          </div>
        </div>

        <div class="action-buttons">
          <Button variant="primary" @click="navigateToResult">
            查看结果
          </Button>
          <Button variant="secondary" @click="clearTask">
            清除任务
          </Button>
        </div>
      </div>

      <!-- 任务已取消 -->
      <div v-else-if="currentTask.status === 'cancelled'" class="task-cancelled">
        <div class="status-icon warning">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <circle cx="12" cy="12" r="10" />
            <line x1="15" y1="9" x2="9" y2="15" />
            <line x1="9" y1="9" x2="15" y2="15" />
          </svg>
        </div>
        <h3 class="status-title">任务已取消</h3>
        <p class="status-message">任务已被用户手动终止</p>

        <div class="task-details">
          <div class="detail-item">
            <span class="detail-label">任务类型</span>
            <span class="detail-value">{{ getTaskTypeLabel(currentTask.type) }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">最后进度</span>
            <span class="detail-value">{{ currentTask.progress }}%</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">创建时间</span>
            <span class="detail-value">{{ formatTime(currentTask.createdAt) }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">取消时间</span>
            <span class="detail-value">{{ formatTime(currentTask.lastUpdatedAt) }}</span>
          </div>
        </div>

        <div class="action-buttons">
          <Button variant="secondary" @click="clearTask">
            清除任务
          </Button>
        </div>
      </div>

      <!-- 任务失败 -->
      <div v-else-if="currentTask.status === 'failed'" class="task-failed">
        <div class="status-icon error">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <circle cx="12" cy="12" r="10" />
            <line x1="15" y1="9" x2="9" y2="15" />
            <line x1="9" y1="9" x2="15" y2="15" />
          </svg>
        </div>
        <h3 class="status-title">任务失败</h3>
        <p class="status-message">{{ currentTask.error || '任务执行失败' }}</p>

        <div class="interrupt-info" v-if="currentTask.interruptType">
          <p class="interrupt-label">失败原因</p>
          <p class="interrupt-message">{{ getInterruptMessage(currentTask.interruptType) }}</p>
        </div>

        <div class="task-details">
          <div class="detail-item">
            <span class="detail-label">任务类型</span>
            <span class="detail-value">{{ getTaskTypeLabel(currentTask.type) }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">创建时间</span>
            <span class="detail-value">{{ formatTime(currentTask.createdAt) }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">失败时间</span>
            <span class="detail-value">{{ formatTime(currentTask.interruptedAt || currentTask.lastUpdatedAt) }}</span>
          </div>
        </div>

        <div class="action-buttons">
          <Button variant="secondary" @click="clearTask">
            清除任务
          </Button>
        </div>
      </div>

      <!-- 前端中断状态 -->
      <div v-else-if="currentTask.status === 'frontend_interrupted'" class="task-interrupted">
        <div class="status-icon warning">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3.05h16.94a2 2 0 0 0 1.71-3.05L13.71 3.86a2 2 0 0 0-3.42 0z" />
            <line x1="12" y1="9" x2="12" y2="13" />
            <line x1="12" y1="17" x2="12.01" y2="17" />
          </svg>
        </div>
        <h3 class="status-title">任务已中断</h3>
        <p class="status-message">前端连接已断开，任务可能仍在后台运行</p>

        <div class="interrupt-info">
          <p class="interrupt-label">中断原因</p>
          <p class="interrupt-message">{{ getInterruptMessage(currentTask.interruptType) }}</p>
        </div>

        <div class="task-details">
          <div class="detail-item">
            <span class="detail-label">任务类型</span>
            <span class="detail-value">{{ getTaskTypeLabel(currentTask.type) }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">最后进度</span>
            <span class="detail-value">{{ currentTask.progress }}%</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">创建时间</span>
            <span class="detail-value">{{ formatTime(currentTask.createdAt) }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">中断时间</span>
            <span class="detail-value">{{ formatTime(currentTask.interruptedAt || currentTask.lastUpdatedAt) }}</span>
          </div>
        </div>

        <div class="action-buttons">
          <Button variant="secondary" @click="clearTask">
            清除任务
          </Button>
        </div>
      </div>
    </Card>

    <!-- 终止任务确认对话框 -->
    <div v-if="showStopConfirm" class="modal-overlay" @click="showStopConfirm = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>确认终止任务</h3>
        </div>
        <div class="modal-body">
          <p>确定要终止当前任务吗？</p>
          <p class="modal-warning">任务终止后将无法恢复，已处理的数据可能会丢失。</p>
        </div>
        <div class="modal-footer">
          <Button variant="secondary" @click="showStopConfirm = false">
            取消
          </Button>
          <Button variant="danger" @click="stopTask">
            确定终止
          </Button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import Card from '@/components/common/Card.vue'
import Button from '@/components/common/Button.vue'
import { taskManager } from '@/services/taskManager'
import { INTERRUPT_MESSAGES } from '@/constants'
import type { EnhancedTask } from '@/types'

const router = useRouter()

// 当前任务状态
const currentTask = ref<EnhancedTask | null>(null)

// 已运行时间（秒）
const elapsedSeconds = ref(0)

// 订阅任务更新
let unsubscribe: (() => void) | null = null

// 计时器ID
let timerInterval: number | null = null

// 终止任务相关状态
const showStopConfirm = ref(false)
const isStopping = ref(false)

/**
 * 【第七步】任务进度展示页面的设计
 *
 * 【关键原则】
 * 页面在进入和离开时，不得触发任何与 TaskManager 或 Worker 创建、销毁、重置相关的逻辑。
 * 页面只负责展示当前任务状态，通过订阅机制获取最新状态。
 *
 * 【生命周期说明】
 * - onMounted: 获取当前任务状态并订阅更新，不创建或修改 TaskManager
 * - onUnmounted: 取消订阅，不销毁或重置 TaskManager
 * - 页面切换时，TaskManager 的状态保持不变
 * - 即使页面卸载，后台任务仍然继续运行
 */

/**
 * 初始化组件
 * 获取当前任务状态并订阅更新
 *
 * 【关键】此方法只负责读取状态，不修改 TaskManager
 */
onMounted(() => {
  // 获取当前任务状态
  currentTask.value = taskManager.getCurrentTask()

  // 订阅任务状态变化
  unsubscribe = taskManager.subscribeToTask((task) => {
    currentTask.value = task
  })

  // 启动计时器，用于显示已运行时间
  startTimer()
})

/**
 * 清理组件
 * 取消订阅和停止计时器
 *
 * 【关键】此方法只负责清理页面级别的资源，不影响 TaskManager
 */
onUnmounted(() => {
  // 取消订阅
  if (unsubscribe) {
    unsubscribe()
  }

  // 停止计时器
  stopTimer()
})

/**
 * 启动计时器
 * 每秒更新已运行时间
 */
const startTimer = () => {
  timerInterval = window.setInterval(() => {
    if (currentTask.value && currentTask.value.status === 'running') {
      const now = Date.now()
      const elapsed = Math.floor((now - currentTask.value.createdAt) / 1000)
      elapsedSeconds.value = elapsed
    }
  }, 1000)
}

/**
 * 停止计时器
 */
const stopTimer = () => {
  if (timerInterval !== null) {
    clearInterval(timerInterval)
    timerInterval = null
  }
}

/**
 * 计算已运行时间的显示格式
 */
const elapsedTime = computed(() => {
  const seconds = elapsedSeconds.value
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secs = seconds % 60

  if (hours > 0) {
    return `${hours}小时${minutes}分钟${secs}秒`
  } else if (minutes > 0) {
    return `${minutes}分钟${secs}秒`
  } else {
    return `${secs}秒`
  }
})

/**
 * 获取任务类型的显示标签
 */
const getTaskTypeLabel = (type: string): string => {
  const labels: Record<string, string> = {
    detection: '检测任务',
    unsupervised: '非监督分类任务',
  }
  return labels[type] || '未知任务'
}

/**
 * 获取中断原因的显示信息
 */
const getInterruptMessage = (interruptType: string): string => {
  return INTERRUPT_MESSAGES[interruptType as keyof typeof INTERRUPT_MESSAGES] || '未知原因'
}

/**
 * 格式化时间戳为可读的时间字符串
 */
const formatTime = (timestamp: number): string => {
  const date = new Date(timestamp)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

/**
 * 导航到结果页面
 * 根据任务类型跳转到相应的结果展示页面
 */
const navigateToResult = () => {
  if (!currentTask.value) return

  if (currentTask.value.type === 'detection') {
    router.push('/detection/result')
  } else if (currentTask.value.type === 'unsupervised') {
    router.push('/unsupervised/result')
  }
}

/**
 * 清除当前任务
 * 清除任务状态和持久化存储
 */
const clearTask = () => {
  taskManager.clearTask()
  currentTask.value = null
}

/**
 * 停止任务
 * 调用后端API终止正在运行的任务
 */
const stopTask = async () => {
  if (!currentTask.value) return

  // 关闭确认对话框
  showStopConfirm.value = false

  // 设置停止中状态
  isStopping.value = true

  try {
    const response = await fetch(`/api/tasks/stop/${currentTask.value.id}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || '停止任务失败')
    }

    const result = await response.json()
    console.log('任务已终止:', result)

    // 显示成功提示
    alert('任务已成功终止')
  } catch (error) {
    console.error('停止任务失败:', error)
    alert(`停止任务失败: ${error instanceof Error ? error.message : '未知错误'}`)
  } finally {
    isStopping.value = false
  }
}
</script>

<style scoped>
.task-progress-page {
  display: flex;
  justify-content: center;
  padding: 24px;
}

.progress-card {
  width: 100%;
  max-width: 800px;
}

.card-header {
  margin-bottom: 32px;
}

.card-header h2 {
  font-size: 24px;
  font-weight: 600;
  color: #333;
  margin-bottom: 8px;
}

.description {
  font-size: 14px;
  color: #999;
  margin: 0;
}

/* ============ 空状态 ============ */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
}

.empty-icon {
  width: 80px;
  height: 80px;
  margin-bottom: 16px;
  color: #d0d0d0;
}

.empty-icon svg {
  width: 100%;
  height: 100%;
  stroke-width: 1.5;
}

.empty-text {
  font-size: 18px;
  font-weight: 500;
  color: #666;
  margin: 0 0 8px 0;
}

.empty-hint {
  font-size: 14px;
  color: #999;
  margin: 0;
}

/* ============ 任务运行中 ============ */
.task-running {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.task-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding-bottom: 16px;
  border-bottom: 1px solid #f0f0f0;
}

.task-info {
  flex: 1;
}

.task-title {
  font-size: 18px;
  font-weight: 600;
  color: #333;
  margin: 0 0 8px 0;
}

.task-id {
  font-size: 12px;
  color: #999;
  margin: 0;
  font-family: monospace;
}

.task-time {
  text-align: right;
}

.time-label {
  font-size: 12px;
  color: #999;
  margin: 0 0 4px 0;
}

.time-value {
  font-size: 16px;
  font-weight: 600;
  color: #0066cc;
  margin: 0;
}

/* ============ 进度条 ============ */
.progress-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.progress-label {
  font-size: 14px;
  font-weight: 500;
  color: #333;
}

.progress-percentage {
  font-size: 14px;
  font-weight: 600;
  color: #0066cc;
}

.progress-bar-container {
  width: 100%;
  height: 8px;
  background-color: #f0f0f0;
  border-radius: 4px;
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  background: linear-gradient(90deg, #0066cc, #0052a3);
  border-radius: 4px;
  transition: width 0.3s ease;
}

/* ============ 任务详情 ============ */
.task-details {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  padding: 16px;
  background-color: #f9f9f9;
  border-radius: 8px;
}

.detail-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.detail-label {
  font-size: 12px;
  color: #999;
  font-weight: 500;
}

.detail-value {
  font-size: 14px;
  color: #333;
  font-weight: 500;
}

/* ============ 状态图标 ============ */
.status-icon {
  width: 80px;
  height: 80px;
  margin: 0 auto 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
}

.status-icon.success {
  background-color: #f0f9ff;
  color: #0066cc;
}

.status-icon.error {
  background-color: #fff5f5;
  color: #ff3b30;
}

.status-icon.warning {
  background-color: #fffbf0;
  color: #ff9500;
}

.status-icon svg {
  width: 48px;
  height: 48px;
  stroke-width: 2;
}

/* ============ 完成/失败/中断/取消状态 ============ */
.task-completed,
.task-failed,
.task-interrupted,
.task-cancelled {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 16px;
}

.status-title {
  font-size: 20px;
  font-weight: 600;
  color: #333;
  margin: 0;
}

.status-message {
  font-size: 14px;
  color: #666;
  margin: 0;
}

/* ============ 中断信息 ============ */
.interrupt-info {
  width: 100%;
  padding: 12px;
  background-color: #fffbf0;
  border-left: 4px solid #ff9500;
  border-radius: 4px;
}

.interrupt-label {
  font-size: 12px;
  color: #999;
  font-weight: 500;
  margin: 0 0 4px 0;
}

.interrupt-message {
  font-size: 14px;
  color: #ff9500;
  margin: 0;
}

/* ============ 操作按钮 ============ */
.action-buttons {
  display: flex;
  gap: 12px;
  justify-content: center;
  width: 100%;
}

.action-buttons button {
  min-width: 120px;
}

/* ============ 模态框 ============ */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  border-radius: 12px;
  padding: 24px;
  max-width: 400px;
  width: 90%;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
}

.modal-header h3 {
  font-size: 18px;
  font-weight: 600;
  color: #333;
  margin: 0 0 16px 0;
}

.modal-body {
  margin-bottom: 24px;
}

.modal-body p {
  font-size: 14px;
  color: #666;
  margin: 0 0 8px 0;
}

.modal-warning {
  font-size: 13px;
  color: #ff9500;
  background-color: #fffbf0;
  padding: 8px 12px;
  border-radius: 4px;
  border-left: 3px solid #ff9500;
}

.modal-footer {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
}

.modal-footer button {
  min-width: 80px;
}
</style>
