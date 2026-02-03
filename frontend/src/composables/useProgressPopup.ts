import { ref, computed } from 'vue'
import { INTERRUPT_TYPES, INTERRUPT_MESSAGES } from '@/constants'
import type { InterruptType } from '@/types'

interface ProgressState {
  isVisible: boolean
  taskType: 'detection' | 'unsupervised'
  progress: number
  currentStage: string
  // 状态：processing(处理中) | completed(完成) | failed(失败) | frontend_interrupted(前端假中断)
  status: 'processing' | 'completed' | 'failed' | 'frontend_interrupted'
  taskId?: string
  // ============ 中断类型字段 ============
  // 用于区分前端假中断与后端真中断，影响UI展示文案
  interruptType?: InterruptType
}

const progressState = ref<ProgressState>({
  isVisible: false,
  taskType: 'detection',
  progress: 0,
  currentStage: '',
  status: 'processing',
})

let pollInterval: ReturnType<typeof setInterval> | null = null

export const useProgressPopup = () => {
  const isVisible = computed(() => progressState.value.isVisible)
  const taskType = computed(() => progressState.value.taskType)
  const progress = computed(() => progressState.value.progress)
  const currentStage = computed(() => progressState.value.currentStage)
  const status = computed(() => progressState.value.status)
  // 获取中断类型
  const interruptType = computed(() => progressState.value.interruptType)

  const showPopup = (type: 'detection' | 'unsupervised') => {
    progressState.value = {
      isVisible: true,
      taskType: type,
      progress: 0,
      currentStage: '',
      status: 'processing',
    }
  }

  const updateProgress = (newProgress: number, stage?: string) => {
    progressState.value.progress = Math.min(100, Math.max(0, newProgress))
    if (stage) {
      progressState.value.currentStage = stage
    }
  }

  const setCompleted = () => {
    progressState.value.progress = 100
    progressState.value.status = 'completed'
    progressState.value.currentStage = '处理完成'
    // 清除中断类型
    progressState.value.interruptType = undefined
  }

  /**
   * 标记为后端真中断（任务失败）
   * @param message 错误信息
   * @param interruptType 中断类型，用于区分具体的失败原因
   */
  const setFailed = (message?: string, interruptType?: InterruptType) => {
    progressState.value.status = 'failed'
    progressState.value.currentStage = message || '处理失败'
    progressState.value.interruptType = interruptType
  }

  /**
   * 标记为前端假中断
   * 当页面刷新、路由切换等导致前端连接丢失时调用
   * @param interruptType 前端假中断类型
   */
  const setFrontendInterrupted = (interruptType: InterruptType) => {
    progressState.value.status = 'frontend_interrupted'
    progressState.value.interruptType = interruptType
    // 根据中断类型设置提示文案
    progressState.value.currentStage = INTERRUPT_MESSAGES[interruptType] || '前端连接已断开'
  }

  const closePopup = () => {
    if (pollInterval) {
      clearInterval(pollInterval)
      pollInterval = null
    }
    progressState.value.isVisible = false
  }

  const startPolling = async (
    taskId: string,
    pollFn: (taskId: string) => Promise<{ progress: number; stage: string; status: string }>
  ) => {
    progressState.value.taskId = taskId

    if (pollInterval) {
      clearInterval(pollInterval)
    }

    pollInterval = setInterval(async () => {
      try {
        const result = await pollFn(taskId)
        updateProgress(result.progress, result.stage)

        if (result.status === 'completed') {
          setCompleted()
          clearInterval(pollInterval)
          pollInterval = null
          setTimeout(() => {
            closePopup()
          }, 1500)
        } else if (result.status === 'failed') {
          setFailed(result.stage)
          clearInterval(pollInterval)
          pollInterval = null
        }
      } catch (error) {
        console.error('轮询进度失败:', error)
      }
    }, 500)
  }

  return {
    isVisible,
    taskType,
    progress,
    currentStage,
    status,
    interruptType,
    showPopup,
    updateProgress,
    setCompleted,
    setFailed,
    setFrontendInterrupted,
    closePopup,
    startPolling,
  }
}
