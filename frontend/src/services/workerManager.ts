/**
 * Worker管理服务
 *
 * 职责：
 * 1. 创建和管理Web Worker实例
 * 2. 处理Worker消息，区分进度、成功和错误
 * 3. 将Worker错误映射到中断类型
 * 4. 与TaskManager协作，标记后端真中断
 */

import { taskManager } from './taskManager'
import { INTERRUPT_TYPES } from '@/constants'
import type { InterruptType } from '@/types'

// ============ Worker消息类型 ============

interface WorkerProgressMessage {
  type: 'progress'
  taskId: string
  progress: number
  stage: string
}

interface WorkerSuccessMessage {
  type: 'success'
  taskId: string
  result: any
}

interface WorkerErrorMessage {
  type: 'error'
  taskId: string
  errorCode: string
  errorMessage: string
  timestamp: number
}

type WorkerMessage = WorkerProgressMessage | WorkerSuccessMessage | WorkerErrorMessage

// ============ Worker错误代码到中断类型的映射 ============

const ERROR_CODE_TO_INTERRUPT_TYPE: Record<string, InterruptType> = {
  COMPUTATION_ERROR: INTERRUPT_TYPES.BACKEND_COMPUTATION_ERROR,
  TIMEOUT: INTERRUPT_TYPES.BACKEND_TIMEOUT,
  TASK_ABORTED: INTERRUPT_TYPES.BACKEND_MANUAL_ABORT,
  UNKNOWN_ERROR: INTERRUPT_TYPES.BACKEND_WORKER_CRASH,
}

// ============ Worker管理类 ============

class WorkerManager {
  private worker: Worker | null = null
  private activeTaskIds = new Set<string>()
  private messageHandlers = new Map<string, (message: WorkerMessage) => void>()

  /**
   * 初始化Worker
   */
  initialize(): void {
    try {
      // 创建Worker实例
      // 注意：在实际项目中，需要配置webpack/vite来正确处理Worker文件
      this.worker = new Worker(new URL('./computeWorker.ts', import.meta.url), {
        type: 'module',
      })

      // 设置Worker消息处理器
      this.worker.onmessage = (event: MessageEvent<WorkerMessage>) => {
        this.handleWorkerMessage(event.data)
      }

      // 设置Worker错误处理器
      this.worker.onerror = (error: ErrorEvent) => {
        console.error('Worker错误:', error.message)
        // 通知所有活跃任务Worker已崩溃
        this.activeTaskIds.forEach((taskId) => {
          this.handleWorkerError(taskId, 'UNKNOWN_ERROR', `Worker崩溃: ${error.message}`)
        })
      }

      console.log('Worker已初始化')
    } catch (error) {
      console.error('初始化Worker失败:', error)
      // 如果Worker初始化失败，系统仍可继续运行，但无法使用Worker功能
    }
  }

  /**
   * 启动计算任务
   * @param taskId 任务ID
   * @param data 任务数据
   * @param onProgress 进度回调
   * @param onSuccess 成功回调
   * @param onError 错误回调
   */
  startComputeTask(
    taskId: string,
    data: any,
    onProgress: (progress: number, stage: string) => void,
    onSuccess: (result: any) => void,
    onError: (errorCode: string, errorMessage: string) => void
  ): void {
    if (!this.worker) {
      onError('WORKER_NOT_AVAILABLE', 'Worker未初始化')
      return
    }

    // 记录活跃任务
    this.activeTaskIds.add(taskId)

    // 设置消息处理器
    this.messageHandlers.set(taskId, (message: WorkerMessage) => {
      if (message.type === 'progress') {
        onProgress(message.progress, message.stage)
      } else if (message.type === 'success') {
        onSuccess(message.result)
        // 任务完成，移除活跃任务记录
        this.activeTaskIds.delete(taskId)
        this.messageHandlers.delete(taskId)
      } else if (message.type === 'error') {
        onError(message.errorCode, message.errorMessage)
        // 任务失败，移除活跃任务记录
        this.activeTaskIds.delete(taskId)
        this.messageHandlers.delete(taskId)
      }
    })

    // 向Worker发送任务
    this.worker.postMessage({
      taskId,
      type: 'compute',
      data,
    })
  }

  /**
   * 中止任务
   * @param taskId 任务ID
   */
  abortTask(taskId: string): void {
    if (!this.worker) return

    this.worker.postMessage({
      taskId,
      type: 'abort',
    })

    // 清理任务记录
    this.activeTaskIds.delete(taskId)
    this.messageHandlers.delete(taskId)
  }

  /**
   * 处理Worker消息
   */
  private handleWorkerMessage(message: WorkerMessage): void {
    const handler = this.messageHandlers.get(message.taskId)
    if (handler) {
      handler(message)
    }
  }

  /**
   * 处理Worker错误
   * 将Worker错误映射到中断类型，并标记为后端真中断
   */
  private handleWorkerError(
    taskId: string,
    errorCode: string,
    errorMessage: string
  ): void {
    // 将错误代码映射到中断类型
    const interruptType = ERROR_CODE_TO_INTERRUPT_TYPE[errorCode] || INTERRUPT_TYPES.BACKEND_WORKER_CRASH

    // 通知TaskManager这是后端真中断
    taskManager.markBackendInterrupt(interruptType, errorMessage)

    // 调用错误处理器
    const handler = this.messageHandlers.get(taskId)
    if (handler) {
      handler({
        type: 'error',
        taskId,
        errorCode,
        errorMessage,
        timestamp: Date.now(),
      })
    }
  }

  /**
   * 销毁Worker
   */
  destroy(): void {
    if (this.worker) {
      this.worker.terminate()
      this.worker = null
      this.activeTaskIds.clear()
      this.messageHandlers.clear()
      console.log('Worker已销毁')
    }
  }
}

// 导出单例
export const workerManager = new WorkerManager()
