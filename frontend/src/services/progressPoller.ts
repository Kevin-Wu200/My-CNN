/**
 * 后端进度轮询服务
 *
 * 功能说明：
 * - 每10秒向后端查询一次任务进度
 * - 自动更新前端任务状态
 * - 任务完成或失败后自动停止轮询
 * - 支持多个任务同时轮询
 */

import type { EnhancedTask } from '@/types'

// 轮询间隔（毫秒）
const POLL_INTERVAL = 10000

// 重试配置
const MAX_RETRIES = 3
const INITIAL_RETRY_DELAY = 2000  // 2秒
const MAX_RETRY_DELAY = 30000     // 30秒

// 后端API基础URL
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

/**
 * 后端任务状态响应格式
 */
interface BackendTaskStatus {
  task_id: string
  task_type: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  progress: number
  current_stage: string
  created_at: string
  started_at: string | null
  completed_at: string | null
  result: any
  error: string | null
}

/**
 * 轮询器配置
 */
interface PollerConfig {
  taskId: string
  onProgress?: (progress: number, stage: string) => void
  onComplete?: (result: any) => void
  onError?: (error: string) => void
  onStop?: () => void
}

/**
 * 进度轮询器类
 */
class ProgressPoller {
  private pollers = new Map<string, NodeJS.Timeout>()
  private activePolls = new Set<string>()
  private retryCount = new Map<string, number>()
  private retryTimeouts = new Map<string, NodeJS.Timeout>()

  /**
   * 启动轮询
   *
   * @param config 轮询配置
   */
  startPolling(config: PollerConfig): void {
    const { taskId, onProgress, onComplete, onError, onStop } = config

    // 如果已经在轮询，则跳过
    if (this.activePolls.has(taskId)) {
      console.log(`[ProgressPoller] 任务 ${taskId} 已在轮询中，跳过重复启动`)
      return
    }

    console.log(`[ProgressPoller] 启动轮询: ${taskId}`)
    this.activePolls.add(taskId)

    // 立即执行一次查询
    this.pollOnce(taskId, onProgress, onComplete, onError)

    // 设置定时轮询
    const pollerId = setInterval(() => {
      this.pollOnce(taskId, onProgress, onComplete, onError, () => {
        // 轮询完成后的回调
        // 如果任务已完成或失败，停止轮询
        if (!this.activePolls.has(taskId)) {
          clearInterval(pollerId)
          this.pollers.delete(taskId)
          onStop?.()
        }
      })
    }, POLL_INTERVAL)

    this.pollers.set(taskId, pollerId)
  }

  /**
   * 执行一次轮询查询
   */
  private async pollOnce(
    taskId: string,
    onProgress?: (progress: number, stage: string) => void,
    onComplete?: (result: any) => void,
    onError?: (error: string) => void,
    onFinish?: () => void
  ): Promise<void> {
    try {
      const response = await fetch(`${API_BASE_URL}/tasks/status/${taskId}`)

      if (!response.ok) {
        if (response.status === 404) {
          // 任务不存在，可能是前端任务或任务已清理
          console.log(`[ProgressPoller] 任务 ${taskId} 在后端不存在`)
          onFinish?.()
          return
        }
        // 后端不可达（5xx 错误或连接失败），停止轮询
        console.error(`[ProgressPoller] 后端不可达: ${taskId} (HTTP ${response.status})`)
        onError?.(`后端服务不可达 (HTTP ${response.status})`)
        this.stopPolling(taskId)
        onFinish?.()
        return
      }

      const backendTask: BackendTaskStatus = await response.json()

      // 重置重试计数（成功获取响应）
      this.retryCount.set(taskId, 0)

      console.log(`[ProgressPoller] 收到后端进度: ${taskId}`, {
        progress: backendTask.progress,
        stage: backendTask.current_stage,
        status: backendTask.status,
      })

      // 更新进度
      if (backendTask.status === 'running') {
        onProgress?.(backendTask.progress, backendTask.current_stage)
      } else if (backendTask.status === 'completed') {
        // 任务完成
        onProgress?.(100, '处理完成')
        onComplete?.(backendTask.result)
        this.stopPolling(taskId)
      } else if (backendTask.status === 'failed') {
        // 任务失败
        onError?.(backendTask.error || '任务失败')
        this.stopPolling(taskId)
      } else if (backendTask.status === 'cancelled') {
        // 任务已取消
        onError?.(backendTask.error || '任务已被取消')
        this.stopPolling(taskId)
      }

      onFinish?.()
    } catch (error) {
      console.error(`[ProgressPoller] 轮询异常: ${taskId}`, error)

      const currentRetries = this.retryCount.get(taskId) || 0

      if (currentRetries < MAX_RETRIES) {
        const retryDelay = Math.min(
          INITIAL_RETRY_DELAY * Math.pow(2, currentRetries),
          MAX_RETRY_DELAY
        )

        this.retryCount.set(taskId, currentRetries + 1)

        console.log(
          `[ProgressPoller] 将在 ${retryDelay}ms 后重试 (${currentRetries + 1}/${MAX_RETRIES}): ${taskId}`
        )

        const retryTimeout = setTimeout(() => {
          this.pollOnce(taskId, onProgress, onComplete, onError, onFinish)
          this.retryTimeouts.delete(taskId)
        }, retryDelay)

        this.retryTimeouts.set(taskId, retryTimeout)
      } else {
        console.error(`[ProgressPoller] 达到最大重试次数，停止轮询: ${taskId}`)
        onError?.(`轮询失败: ${error instanceof Error ? error.message : '未知错误'}（已重试${MAX_RETRIES}次）`)
        this.stopPolling(taskId)
      }

      onFinish?.()
    }
  }

  /**
   * 停止轮询
   */
  stopPolling(taskId: string): void {
    if (this.activePolls.has(taskId)) {
      console.log(`[ProgressPoller] 停止轮询: ${taskId}`)
      const pollerId = this.pollers.get(taskId)
      if (pollerId) {
        clearInterval(pollerId)
        this.pollers.delete(taskId)
      }

      const retryTimeout = this.retryTimeouts.get(taskId)
      if (retryTimeout) {
        clearTimeout(retryTimeout)
        this.retryTimeouts.delete(taskId)
      }
      this.retryCount.delete(taskId)
      this.activePolls.delete(taskId)
    }
  }

  /**
   * 停止所有轮询
   */
  stopAllPolling(): void {
    console.log(`[ProgressPoller] 停止所有轮询`)
    this.pollers.forEach((pollerId) => {
      clearInterval(pollerId)
    })
    this.pollers.clear()
    this.activePolls.clear()
  }

  /**
   * 检查是否正在轮询
   */
  isPolling(taskId: string): boolean {
    return this.activePolls.has(taskId)
  }
}

// 全局轮询器实例
export const progressPoller = new ProgressPoller()
