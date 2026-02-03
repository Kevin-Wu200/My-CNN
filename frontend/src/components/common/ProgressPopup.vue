<template>
  <Teleport to="body">
    <div
      v-if="isVisible"
      class="progress-popup"
      :style="popupStyle"
      @mousedown="startDrag"
    >
      <!-- 拖拽条 -->
      <div class="popup-header" @mousedown="startDrag">
        <div class="header-content">
          <div class="task-icon">
            <svg v-if="taskType === 'detection'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10" />
              <polyline points="12 6 12 12 16 14" />
            </svg>
            <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="1" />
              <circle cx="19" cy="12" r="1" />
              <circle cx="5" cy="12" r="1" />
            </svg>
          </div>
          <div class="header-text">
            <p class="task-title">{{ taskTitle }}</p>
            <p class="task-status">{{ currentStage || '处理中，请稍候' }}</p>
          </div>
        </div>
        <button class="close-btn" @click="closePopup" v-if="status === 'failed' || status === 'frontend_interrupted'">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      </div>

      <!-- 进度条 -->
      <div class="progress-section">
        <div class="progress-bar-container">
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: `${progress}%` }"></div>
          </div>
        </div>
        <p class="progress-text">{{ progress }}%</p>
      </div>

      <!-- 阶段提示 -->
      <div v-if="currentStage && status === 'processing'" class="stage-hint">
        {{ currentStage }}
      </div>

      <!-- 状态提示 - 处理完成 -->
      <div v-if="status === 'completed'" class="status-indicator completed">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="20 6 9 17 4 12" />
        </svg>
        <span>处理完成</span>
      </div>

      <!-- 状态提示 - 后端真中断（任务失败） -->
      <div v-else-if="status === 'failed'" class="status-indicator failed">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
        <span>{{ getFailedMessage }}</span>
      </div>

      <!-- 状态提示 - 前端假中断 -->
      <div v-else-if="status === 'frontend_interrupted'" class="status-indicator frontend-interrupted">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm3.5-9c.83 0 1.5-.67 1.5-1.5S16.33 8 15.5 8 14 8.67 14 9.5s.67 1.5 1.5 1.5zm-7 0c.83 0 1.5-.67 1.5-1.5S9.33 8 8.5 8 7 8.67 7 9.5 7.67 11 8.5 11zm3.5 6.5c2.33 0 4.31-1.46 5.11-3.5H6.89c.8 2.04 2.78 3.5 5.11 3.5z" />
        </svg>
        <span>前端连接已断开</span>
      </div>

      <!-- 状态提示 - 处理中 -->
      <div v-else class="status-indicator processing">
        <div class="spinner"></div>
        <span>处理中</span>
      </div>

      <!-- 中断类型详细说明 -->
      <div v-if="showInterruptDetails" class="interrupt-details">
        <p class="interrupt-message">{{ interruptMessage }}</p>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { INTERRUPT_MESSAGES } from '@/constants'
import type { InterruptType } from '@/types'

interface Props {
  isVisible: boolean
  taskType: 'detection' | 'unsupervised'
  progress: number
  currentStage?: string
  // 状态：processing(处理中) | completed(完成) | failed(失败) | frontend_interrupted(前端假中断)
  status: 'processing' | 'completed' | 'failed' | 'frontend_interrupted'
  // 中断类型，用于区分前端假中断与后端真中断
  interruptType?: InterruptType
}

interface Emits {
  (e: 'close'): void
}

const props = withDefaults(defineProps<Props>(), {
  progress: 0,
  status: 'processing',
})

const emit = defineEmits<Emits>()

const isDragging = ref(false)
const dragOffset = ref({ x: 0, y: 0 })
const position = ref({ x: 0, y: 0 })

const taskTitle = computed(() => {
  return props.taskType === 'detection' ? '深度学习检测处理中' : '非监督分类处理中'
})

const popupStyle = computed(() => ({
  transform: `translate(${position.value.x}px, ${position.value.y}px)`,
}))

/**
 * 获取失败状态的显示文案
 * 根据中断类型区分后端真中断的具体原因
 */
const getFailedMessage = computed(() => {
  if (props.interruptType && INTERRUPT_MESSAGES[props.interruptType]) {
    return INTERRUPT_MESSAGES[props.interruptType]
  }
  return '处理失败'
})

/**
 * 获取中断详细说明
 * 为用户提供更清晰的中断原因解释
 */
const interruptMessage = computed(() => {
  if (!props.interruptType) return ''
  return INTERRUPT_MESSAGES[props.interruptType] || ''
})

/**
 * 判断是否显示中断详细说明
 * 前端假中断和后端真中断都需要显示详细说明
 */
const showInterruptDetails = computed(() => {
  return (props.status === 'failed' || props.status === 'frontend_interrupted') && props.interruptType
})

const startDrag = (event: MouseEvent) => {
  if ((event.target as HTMLElement).closest('.close-btn')) {
    return
  }
  isDragging.value = true
  dragOffset.value = {
    x: event.clientX - position.value.x,
    y: event.clientY - position.value.y,
  }
}

const handleMouseMove = (event: MouseEvent) => {
  if (!isDragging.value) return
  position.value = {
    x: event.clientX - dragOffset.value.x,
    y: event.clientY - dragOffset.value.y,
  }
}

const handleMouseUp = () => {
  isDragging.value = false
}

const closePopup = () => {
  emit('close')
}

onMounted(() => {
  // 初始位置：右下角
  position.value = {
    x: window.innerWidth - 320,
    y: window.innerHeight - 200,
  }
  document.addEventListener('mousemove', handleMouseMove)
  document.addEventListener('mouseup', handleMouseUp)
})

onUnmounted(() => {
  document.removeEventListener('mousemove', handleMouseMove)
  document.removeEventListener('mouseup', handleMouseUp)
})
</script>

<style scoped>
.progress-popup {
  position: fixed;
  width: 300px;
  background: white;
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
  z-index: 9999;
  user-select: none;
  overflow: hidden;
}

.popup-header {
  padding: 12px 16px;
  background: #f9f9f9;
  border-bottom: 1px solid #e8e8e8;
  cursor: move;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-content {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
}

.task-icon {
  width: 24px;
  height: 24px;
  color: #0066cc;
  flex-shrink: 0;
}

.task-icon svg {
  width: 100%;
  height: 100%;
}

.header-text {
  flex: 1;
  min-width: 0;
}

.task-title {
  font-size: 13px;
  font-weight: 600;
  color: #333;
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.task-status {
  font-size: 12px;
  color: #999;
  margin: 2px 0 0 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.close-btn {
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  cursor: pointer;
  color: #999;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color 0.2s;
  flex-shrink: 0;
}

.close-btn:hover {
  color: #333;
}

.close-btn svg {
  width: 16px;
  height: 16px;
}

.progress-section {
  padding: 16px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.progress-bar-container {
  flex: 1;
}

.progress-bar {
  width: 100%;
  height: 6px;
  background: #e8e8e8;
  border-radius: 3px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #0066cc, #0052a3);
  border-radius: 3px;
  transition: width 0.3s ease;
}

.progress-text {
  font-size: 13px;
  font-weight: 600;
  color: #0066cc;
  margin: 0;
  min-width: 35px;
  text-align: right;
}

.stage-hint {
  padding: 0 16px 12px 16px;
  font-size: 12px;
  color: #666;
  text-align: center;
}

.status-indicator {
  padding: 12px 16px;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 500;
  border-top: 1px solid #e8e8e8;
}

.status-indicator svg {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.status-indicator.processing {
  color: #0066cc;
}

.status-indicator.processing svg {
  color: #0066cc;
}

.status-indicator.completed {
  color: #34c759;
}

.status-indicator.completed svg {
  color: #34c759;
}

/* 后端真中断样式 - 红色 */
.status-indicator.failed {
  color: #ff3b30;
}

.status-indicator.failed svg {
  color: #ff3b30;
}

/* 前端假中断样式 - 橙色，与失败区分 */
.status-indicator.frontend-interrupted {
  color: #ff9500;
}

.status-indicator.frontend-interrupted svg {
  color: #ff9500;
}

.spinner {
  width: 14px;
  height: 14px;
  border: 2px solid #0066cc;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

/* 中断详细说明 */
.interrupt-details {
  padding: 8px 16px 12px 16px;
  background: #f5f5f5;
  border-top: 1px solid #e8e8e8;
}

.interrupt-message {
  font-size: 12px;
  color: #666;
  margin: 0;
  line-height: 1.4;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
