import { INTERRUPT_TYPES, INTERRUPT_TYPE_CATEGORIES, INTERRUPT_TYPE_TO_CATEGORY } from '@/constants'
import type { EnhancedTask, PersistedTaskState, InterruptType } from '@/types'
import { uploadManager } from './uploadManager'

// 为了向后兼容，保留原有的Task接口
export interface Task {
  id: string
  type: 'unsupervised' | 'detection'
  status: 'running' | 'completed' | 'failed'
  progress: number
  currentStage: string
  createdAt: number
  result?: any
  error?: string
}

/**
 * ============ 核心架构设计 ============
 *
 * 【第一步】明确任务中断的根源
 * 任务中断不来自 Vue 组件生命周期，而来自模块重新初始化。
 * 当 Vite HMR 或路由动态导入导致模块重新加载时，如果 TaskManager 依赖 ES module 默认单例行为，
 * 会导致模块级变量重新初始化，从而丢失任务状态。
 *
 * 【第二步】强单例实现原则
 * TaskManager 必须被显式挂载到全局运行时对象（window 或 globalThis）。
 * 创建逻辑必须首先检查全局对象上是否已存在实例，若存在则复用，禁止重复 new。
 *
 * 【第三步】强单例语义
 * 无论该模块被 import 多少次、是否发生路由切换或模块重载，都只能存在一个 TaskManager 实例。
 * 这通过全局对象的引用保证，而不是依赖 ES module 的单例行为。
 *
 * 【第四步】Worker 生命周期管理
 * Web Worker 的生命周期必须完全由全局 TaskManager 管理。
 * Worker 的创建、通信和销毁不得依赖任何页面或模块的执行顺序。
 * Worker 实例必须存活于 TaskManager 中，而不是临时变量或函数作用域中。
 *
 * 【第五步】页面访问规则
 * 所有页面和组件只能通过访问全局 TaskManager 实例来读取任务状态或触发任务启动。
 * 不允许在任何页面中创建新的 TaskManager 或 Worker。
 *
 * 【第六步】三种生命周期的独立性
 * 1. Vue 组件生命周期：组件的 mount/unmount，不影响 TaskManager
 * 2. 路由生命周期：路由切换，不影响 TaskManager
 * 3. TaskManager 与 Worker 的运行时生命周期：独立于上述两种，由全局对象维护
 *
 * 【第七步】任务进度展示页面的设计
 * 页面在进入和离开时，不得触发任何与 TaskManager 或 Worker 创建、销毁、重置相关的逻辑。
 * 页面只负责展示当前任务状态，通过订阅机制获取最新状态。
 *
 * 【为什么模块重新执行不会导致任务中断】
 * - TaskManager 实例存储在 window/globalThis 上，不会因为模块重新加载而被销毁
 * - 模块重新加载时，会检查全局对象上是否已存在实例，若存在则复用
 * - 任务状态通过 localStorage 持久化，即使浏览器刷新也能恢复
 * - Worker 实例由 TaskManager 管理，不会因为模块重新加载而被销毁
 */

// ============ 全局对象类型扩展 ============
// 声明全局对象上的 TaskManager 实例属性
declare global {
  interface Window {
    __APP_TASK_MANAGER__?: TaskManagerImpl
  }
}

// ============ 持久化存储键名 ============
const PERSISTED_TASK_KEY = 'app_current_task_state'
const WORKER_INSTANCE_KEY = 'app_worker_instance_id'
const GLOBAL_TASK_MANAGER_KEY = '__APP_TASK_MANAGER__'

// ============ Worker 管理接口 ============
/**
 * Worker 消息类型定义
 */
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

// ============ TaskManager 实现类 ============
/**
 * 【强单例 TaskManager 实现】
 *
 * 这个类实现了以下关键特性：
 * 1. 实例存储在全局对象（window/globalThis）上，不会因为模块重新加载而被销毁
 * 2. 包含完整的 Worker 生命周期管理
 * 3. 使用纯 JavaScript 的观察者模式实现订阅机制
 * 4. 任务状态通过 localStorage 持久化
 */
class TaskManagerImpl {
  // 【关键】实例级别的状态变量
  // 这些变量存储在类实例中，而实例存储在全局对象上
  private currentTask: EnhancedTask | null = null
  private currentWorkerInstanceId: string | null = null
  private subscribers = new Set<(task: EnhancedTask | null) => void>()

  // 【第四步】Worker 生命周期管理
  // Worker 实例由 TaskManager 完全管理，不会因为模块重新加载而被销毁
  private worker: Worker | null = null
  private activeTaskIds = new Set<string>()
  private messageHandlers = new Map<string, (message: WorkerMessage) => void>()

  /**
   * 【第二步】初始化检查
   * 检查全局对象上是否已存在实例，若存在则复用
   * 这确保了强单例语义
   */
  private constructor() {
    console.log('[TaskManager] 创建新的 TaskManager 实例')
  }

  /**
   * 【第二步】获取或创建全局 TaskManager 实例
   * 这是强单例的核心实现
   * 无论该模块被 import 多少次，都只会存在一个实例
   */
  static getInstance(): TaskManagerImpl {
    // 检查全局对象上是否已存在实例
    if (typeof window !== 'undefined' && window[GLOBAL_TASK_MANAGER_KEY as any]) {
      console.log('[TaskManager] 复用已存在的全局 TaskManager 实例')
      return window[GLOBAL_TASK_MANAGER_KEY as any]
    }

    // 创建新实例
    const instance = new TaskManagerImpl()

    // 【关键】显式挂载到全局对象
    // 这确保了即使模块重新加载，实例仍然存在
    if (typeof window !== 'undefined') {
      window[GLOBAL_TASK_MANAGER_KEY as any] = instance
      console.log('[TaskManager] 已将 TaskManager 实例挂载到全局对象')
    }

    return instance
  }

  /**
   * 【第四步】初始化 Worker
   * Worker 的创建由 TaskManager 完全管理
   */
  private initializeWorker(): void {
    try {
      if (this.worker) {
        console.log('[TaskManager] Worker 已存在，跳过初始化')
        return
      }

      // 创建 Worker 实例
      this.worker = new Worker(new URL('./computeWorker.ts', import.meta.url), {
        type: 'module',
      })

      console.log('[TaskManager] Worker 实例已创建')

      // 设置 Worker 消息处理器
      this.worker.onmessage = (event: MessageEvent<WorkerMessage>) => {
        console.log('[TaskManager] Worker onmessage 触发:', {
          messageType: event.data.type,
          taskId: event.data.taskId,
        })
        this.handleWorkerMessage(event.data)
      }

      // 设置 Worker 错误处理器
      this.worker.onerror = (error: ErrorEvent) => {
        console.error('[TaskManager] Worker 错误:', error.message)
        // 通知所有活跃任务 Worker 已崩溃
        this.activeTaskIds.forEach((taskId) => {
          this.handleWorkerError(taskId, 'UNKNOWN_ERROR', `Worker 崩溃: ${error.message}`)
        })
      }

      console.log('[TaskManager] Worker 已初始化')
    } catch (error) {
      console.error('[TaskManager] 初始化 Worker 失败:', error)
    }
  }

  /**
   * 处理 Worker 消息
   */
  private handleWorkerMessage(message: WorkerMessage): void {
    console.log('[TaskManager] 收到 Worker 消息:', {
      type: message.type,
      taskId: message.taskId,
      hasHandler: this.messageHandlers.has(message.taskId),
      activeTaskIds: Array.from(this.activeTaskIds),
    })

    const handler = this.messageHandlers.get(message.taskId)
    if (handler) {
      handler(message)
    } else {
      console.warn('[TaskManager] 未找到任务处理器:', message.taskId)
    }
  }

  /**
   * 处理 Worker 错误
   */
  private handleWorkerError(
    taskId: string,
    errorCode: string,
    errorMessage: string
  ): void {
    // 将错误代码映射到中断类型
    const interruptTypeMap: Record<string, InterruptType> = {
      COMPUTATION_ERROR: INTERRUPT_TYPES.BACKEND_COMPUTATION_ERROR,
      TIMEOUT: INTERRUPT_TYPES.BACKEND_TIMEOUT,
      TASK_ABORTED: INTERRUPT_TYPES.BACKEND_MANUAL_ABORT,
      UNKNOWN_ERROR: INTERRUPT_TYPES.BACKEND_WORKER_CRASH,
    }
    const interruptType = interruptTypeMap[errorCode] || INTERRUPT_TYPES.BACKEND_WORKER_CRASH

    // 通知 TaskManager 这是后端真中断
    this.markBackendInterrupt(interruptType, errorMessage)

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
   * 【第四步】销毁 Worker
   * Worker 的销毁由 TaskManager 完全管理
   */
  private destroyWorker(): void {
    if (this.worker) {
      this.worker.terminate()
      this.worker = null
      this.activeTaskIds.clear()
      this.messageHandlers.clear()
      console.log('[TaskManager] Worker 已销毁')
    }
  }

  // ============ 辅助函数 ============

  /**
   * 生成唯一的任务 ID
   */
  private generateTaskId(): string {
    return `task_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  }

  /**
   * 生成唯一的 Worker 实例 ID
   * 用于判断页面刷新是否导致了前端假中断
   */
  private generateWorkerInstanceId(): string {
    return `worker_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  }

  /**
   * 将任务状态持久化到 localStorage
   * 用于页面刷新后恢复任务状态
   */
  private persistTaskState(task: EnhancedTask): void {
    const persistedState: PersistedTaskState = {
      taskId: task.id,
      taskType: task.type,
      status: task.status,
      progress: task.progress,
      currentStage: task.currentStage,
      createdAt: task.createdAt,
      lastUpdatedAt: task.lastUpdatedAt,
      interruptType: task.interruptType,
      interruptedAt: task.interruptedAt,
      workerInstanceId: this.currentWorkerInstanceId || undefined,
    }
    localStorage.setItem(PERSISTED_TASK_KEY, JSON.stringify(persistedState))
  }

  /**
   * 从 localStorage 恢复任务状态
   * 【关键】检测页面刷新导致的前端假中断
   */
  private restoreTaskState(): EnhancedTask | null {
    try {
      const stored = localStorage.getItem(PERSISTED_TASK_KEY)
      if (!stored) return null

      const persistedState: PersistedTaskState = JSON.parse(stored)

      // 检查是否为前端假中断
      // 如果任务状态为 running 但 Worker 实例已丢失，则标记为前端假中断
      if (persistedState.status === 'running' && persistedState.workerInstanceId) {
        // 比较 Worker 实例 ID，如果不同则说明是页面刷新导致的前端假中断
        if (persistedState.workerInstanceId !== this.currentWorkerInstanceId) {
          persistedState.status = 'frontend_interrupted'
          persistedState.interruptType = INTERRUPT_TYPES.FRONTEND_PAGE_REFRESH
          persistedState.interruptedAt = Date.now()
        }
      }

      const restoredTask: EnhancedTask = {
        id: persistedState.taskId,
        type: persistedState.taskType,
        status: persistedState.status,
        progress: persistedState.progress,
        currentStage: persistedState.currentStage,
        createdAt: persistedState.createdAt,
        lastUpdatedAt: persistedState.lastUpdatedAt,
        interruptType: persistedState.interruptType,
        interruptedAt: persistedState.interruptedAt,
      }

      return restoredTask
    } catch (error) {
      console.error('[TaskManager] 恢复任务状态失败:', error)
      return null
    }
  }

  /**
   * 清除持久化的任务状态
   */
  private clearPersistedTaskState(): void {
    localStorage.removeItem(PERSISTED_TASK_KEY)
  }

  /**
   * 通知所有订阅者任务状态已更新
   * 这是纯 JavaScript 的观察者模式实现，不依赖 Vue 的响应式系统
   */
  private notifySubscribers(): void {
    this.subscribers.forEach((callback) => {
      callback(this.currentTask)
    })
  }

  /**
   * 更新任务状态并通知所有订阅者
   * 这个函数确保任务状态变化时，所有订阅者都能收到通知
   * 同时将状态持久化到 localStorage
   */
  private updateTaskState(task: EnhancedTask | null): void {
    this.currentTask = task
    if (task) {
      this.persistTaskState(task)
    }
    this.notifySubscribers()
  }

  // ============ 公共 API ============

  /**
   * 初始化 TaskManager
   * 在应用启动时调用一次，用于恢复上一次的任务状态
   *
   * 【关键设计】此方法在应用启动时调用一次，不与任何组件生命周期关联
   * 调用位置：main.ts 中，在 app.mount() 之前
   */
  initialize(): void {
    // 【改进】只在初始化时生成一次 Worker 实例 ID
    // 不在启动新任务时覆盖它
    if (!this.currentWorkerInstanceId) {
      this.currentWorkerInstanceId = this.generateWorkerInstanceId()
      console.log('[TaskManager] 生成全局 Worker 实例 ID:', this.currentWorkerInstanceId)
    }

    // 初始化 Worker
    // 【第四步】Worker 的创建由 TaskManager 完全管理
    this.initializeWorker()

    // 尝试从持久化存储恢复任务状态
    const restoredTask = this.restoreTaskState()
    if (restoredTask) {
      this.currentTask = restoredTask
      console.log('[TaskManager] 任务状态已恢复:', restoredTask)
      this.notifySubscribers()
    }
  }
  /**
   * 启动无监督分类任务
   *
   * 【关键设计】
   * - 此方法在组件中被调用，但任务执行逻辑完全在 Worker 中执行
   * - 组件只负责调用此方法，不负责任务的执行和管理
   * - 任务启动后，组件应该立即通过 vue-router 跳转到任务进度页面
   * - 页面切换不会中断任务，因为任务在 Worker 线程中执行，独立于主线程
   *
   * 【改进】文件上传在主线程中执行，获得文件路径后再发送给Worker
   */
  async startUnsupervisedTask(
    file: File,
    params: { nClusters: number; minArea: number }
  ): Promise<string> {
    const taskId = this.generateTaskId()

    console.log('[TaskManager] 启动无监督任务:', {
      taskId,
      workerInstanceId: this.currentWorkerInstanceId,
      workerExists: !!this.worker,
      activeTasksCount: this.activeTaskIds.size,
    })

    // Create enhanced task object with interrupt type support
    const task: EnhancedTask = {
      id: taskId,
      type: 'unsupervised',
      status: 'running',
      progress: 0,
      currentStage: '上传影像中',
      createdAt: Date.now(),
      lastUpdatedAt: Date.now(),
      workerInstanceId: this.currentWorkerInstanceId || undefined,
    }

    this.updateTaskState(task)

    try {
      // 【第一步】使用分片上传文件
      console.log('[TaskManager] 开始分片上传影像文件:', {
        taskId,
        fileName: file.name,
        fileSize: file.size,
      })

      let filePath: string = ''

      // 使用 uploadManager 进行分片上传
      await new Promise<void>((resolve, reject) => {
        uploadManager.uploadFile(file, {
          onProgress: (progress, uploadedChunks, totalChunks) => {
            // 上传进度映射到任务进度的 0-20% 范围
            task.progress = Math.round((progress / 100) * 20)
            task.currentStage = `上传中 (${uploadedChunks}/${totalChunks})`
            task.lastUpdatedAt = Date.now()
            this.updateTaskState(task)

            console.log('[TaskManager] 上传进度:', {
              taskId,
              progress,
              uploadedChunks,
              totalChunks,
              taskProgress: task.progress,
            })
          },
          onComplete: (result) => {
            filePath = result.filePath

            console.log('[TaskManager] 影像文件上传成功:', {
              taskId,
              filePath,
              totalChunks: result.totalChunks,
            })

            // 更新任务状态
            task.progress = 20
            task.currentStage = '影像上传完成，准备检测'
            task.lastUpdatedAt = Date.now()
            this.updateTaskState(task)

            resolve()
          },
          onError: (error) => {
            console.error('[TaskManager] 上传失败:', {
              taskId,
              errorCode: error.code,
              errorMessage: error.message,
            })
            reject(new Error(`上传失败: ${error.message}`))
          },
        }).catch(reject)
      })

      // 【第二步】设置 Worker 消息处理器
      const messageHandler = (message: WorkerMessage) => {
        console.log('[TaskManager] 处理 Worker 消息:', {
          type: message.type,
          taskId: message.taskId,
          progress: (message as any).progress,
          stage: (message as any).stage,
        })

        if (message.type === 'progress') {
          task.progress = message.progress
          task.currentStage = message.stage
          task.lastUpdatedAt = Date.now()
          console.log('[TaskManager] 更新进度:', {
            taskId: task.id,
            progress: task.progress,
            stage: task.currentStage,
          })
          this.updateTaskState(task)
        } else if (message.type === 'success') {
          task.result = message.result
          task.progress = 100
          task.currentStage = '处理完成'
          task.status = 'completed'
          task.lastUpdatedAt = Date.now()
          console.log('[TaskManager] 任务完成:', {
            taskId: task.id,
            progress: task.progress,
          })
          this.updateTaskState(task)

          // Save to sessionStorage for backward compatibility
          sessionStorage.setItem('detectionResult', JSON.stringify(message.result))

          // 任务完成后清除持久化状态
          setTimeout(() => {
            this.clearPersistedTaskState()
          }, 1500)

          // 清理消息处理器
          this.messageHandlers.delete(taskId)
          this.activeTaskIds.delete(taskId)
        } else if (message.type === 'error') {
          const errorMessage = message.errorMessage || '检测失败'

          console.error('[TaskManager] 任务错误:', {
            taskId: task.id,
            errorCode: message.errorCode,
            errorMessage,
          })

          // 标记为后端真中断
          task.status = 'failed'
          task.error = errorMessage
          task.interruptType = INTERRUPT_TYPES.BACKEND_INFERENCE_FAILED
          task.interruptedAt = Date.now()
          task.lastUpdatedAt = Date.now()
          this.updateTaskState(task)

          // 清理消息处理器
          this.messageHandlers.delete(taskId)
          this.activeTaskIds.delete(taskId)
        }
      }

      this.messageHandlers.set(taskId, messageHandler)
      this.activeTaskIds.add(taskId)

      // 【第三步】向 Worker 发送任务（带有文件路径）
      if (this.worker) {
        console.log('[TaskManager] 向 Worker 发送无监督任务:', {
          taskId,
          workerInstanceId: this.currentWorkerInstanceId,
          filePath,
          messageHandlersCount: this.messageHandlers.size,
        })
        this.worker.postMessage({
          taskId,
          type: 'compute',
          data: {
            taskType: 'unsupervised',
            filePath, // 【改进】传递文件路径而不是File对象
            params,
          },
        })
      } else {
        throw new Error('Worker 未初始化')
      }

      return taskId
    } catch (error: any) {
      // 上传失败，标记任务为失败
      console.error('[TaskManager] 无监督任务启动失败:', error)

      task.status = 'failed'
      task.error = error.message || '任务启动失败'
      task.interruptType = INTERRUPT_TYPES.BACKEND_INFERENCE_FAILED
      task.interruptedAt = Date.now()
      task.lastUpdatedAt = Date.now()
      this.updateTaskState(task)

      throw error
    }
  }

  /**
   * 启动检测任务
   *
   * 【关键设计】
   * - 此方法在组件中被调用，但任务执行逻辑完全在 Worker 中执行
   * - 组件只负责调用此方法，不负责任务的执行和管理
   * - 任务启动后，组件应该立即通过 vue-router 跳转到任务进度页面
   * - 页面切换不会中断任务，因为任务在 Worker 线程中执行，独立于主线程
   */
  async startDetectionTask(
    files: File[],
    params: { temporalType: string }
  ): Promise<string> {
    const taskId = this.generateTaskId()

    console.log('[TaskManager] 启动检测任务:', {
      taskId,
      workerInstanceId: this.currentWorkerInstanceId,
      filesCount: files.length,
      workerExists: !!this.worker,
      activeTasksCount: this.activeTaskIds.size,
    })

    // Create enhanced task object with interrupt type support
    const task: EnhancedTask = {
      id: taskId,
      type: 'detection',
      status: 'running',
      progress: 0,
      currentStage: '上传影像中',
      createdAt: Date.now(),
      lastUpdatedAt: Date.now(),
      workerInstanceId: this.currentWorkerInstanceId || undefined,
    }

    this.updateTaskState(task)

    try {
      // 【第一步】使用分片上传所有文件
      console.log('[TaskManager] 开始分片上传检测影像:', {
        taskId,
        filesCount: files.length,
      })

      const uploadedFilePaths: string[] = []
      const totalFileSize = files.reduce((sum, f) => sum + f.size, 0)
      let uploadedSize = 0

      for (let i = 0; i < files.length; i++) {
        const file = files[i]

        await new Promise<void>((resolve, reject) => {
          uploadManager.uploadFile(file, {
            onProgress: (progress, uploadedChunks, totalChunks) => {
              // 计算总体上传进度（0-20%）
              const fileProgress = (progress / 100) * file.size
              const totalProgress = ((uploadedSize + fileProgress) / totalFileSize) * 20

              task.progress = Math.round(totalProgress)
              task.currentStage = `上传中 (${i + 1}/${files.length})`
              task.lastUpdatedAt = Date.now()
              this.updateTaskState(task)

              console.log('[TaskManager] 检测任务上传进度:', {
                taskId,
                fileIndex: i + 1,
                totalFiles: files.length,
                progress: task.progress,
              })
            },
            onComplete: (result) => {
              uploadedFilePaths.push(result.filePath)
              uploadedSize += file.size

              console.log('[TaskManager] 检测影像文件上传成功:', {
                taskId,
                fileIndex: i + 1,
                filePath: result.filePath,
              })

              resolve()
            },
            onError: (error) => {
              console.error('[TaskManager] 检测任务上传失败:', {
                taskId,
                fileIndex: i + 1,
                errorCode: error.code,
                errorMessage: error.message,
              })
              reject(new Error(`文件 ${file.name} 上传失败: ${error.message}`))
            },
          }).catch(reject)
        })
      }

      // 更新任务状态
      task.progress = 20
      task.currentStage = '影像上传完成，准备检测'
      task.lastUpdatedAt = Date.now()
      this.updateTaskState(task)

      // 【第二步】设置 Worker 消息处理器
      const messageHandler = (message: WorkerMessage) => {
        console.log('[TaskManager] 处理 Worker 消息:', {
          type: message.type,
          taskId: message.taskId,
          progress: (message as any).progress,
          stage: (message as any).stage,
        })

        if (message.type === 'progress') {
          // 检测进度映射到 20-100% 范围
          task.progress = 20 + Math.round((message.progress / 100) * 80)
          task.currentStage = message.stage
          task.lastUpdatedAt = Date.now()
          console.log('[TaskManager] 更新进度:', {
            taskId: task.id,
            progress: task.progress,
            stage: task.currentStage,
          })
          this.updateTaskState(task)
        } else if (message.type === 'success') {
          task.result = message.result
          task.progress = 100
          task.currentStage = '处理完成'
          task.status = 'completed'
          task.lastUpdatedAt = Date.now()
          console.log('[TaskManager] 任务完成:', {
            taskId: task.id,
            progress: task.progress,
          })
          this.updateTaskState(task)

          // Save to sessionStorage for backward compatibility
          sessionStorage.setItem('detectionResult', JSON.stringify(message.result))

          // 任务完成后清除持久化状态
          setTimeout(() => {
            this.clearPersistedTaskState()
          }, 1500)

          // 清理消息处理器
          this.messageHandlers.delete(taskId)
          this.activeTaskIds.delete(taskId)
        } else if (message.type === 'error') {
          const errorMessage = message.errorMessage || '检测失败'

          console.error('[TaskManager] 任务错误:', {
            taskId: task.id,
            errorCode: message.errorCode,
            errorMessage,
          })

          // 标记为后端真中断
          task.status = 'failed'
          task.error = errorMessage
          task.interruptType = INTERRUPT_TYPES.BACKEND_INFERENCE_FAILED
          task.interruptedAt = Date.now()
          task.lastUpdatedAt = Date.now()
          this.updateTaskState(task)

          // 清理消息处理器
          this.messageHandlers.delete(taskId)
          this.activeTaskIds.delete(taskId)
        }
      }

      this.messageHandlers.set(taskId, messageHandler)
      this.activeTaskIds.add(taskId)

      // 【第三步】向 Worker 发送任务（带有文件路径）
      if (this.worker) {
        console.log('[TaskManager] 向 Worker 发送检测任务:', {
          taskId,
          workerInstanceId: this.currentWorkerInstanceId,
          filesCount: uploadedFilePaths.length,
          messageHandlersCount: this.messageHandlers.size,
        })
        this.worker.postMessage({
          taskId,
          type: 'compute',
          data: {
            taskType: 'detection',
            filePaths: uploadedFilePaths,
            params,
          },
        })
      } else {
        throw new Error('Worker 未初始化')
      }

      return taskId
    } catch (error: any) {
      // 上传失败，标记任务为失败
      console.error('[TaskManager] 检测任务启动失败:', error)

      task.status = 'failed'
      task.error = error.message || '任务启动失败'
      task.interruptType = INTERRUPT_TYPES.BACKEND_INFERENCE_FAILED
      task.interruptedAt = Date.now()
      task.lastUpdatedAt = Date.now()
      this.updateTaskState(task)

      throw error
    }
  }

  /**
   * 标记任务为前端假中断
   * 当页面刷新、路由切换或组件卸载时调用
   *
   * 【关键设计】
   * - 此方法由路由守卫调用，不由组件直接调用
   * - 标记为前端假中断，表示前端连接丢失，但后端任务可能仍在运行
   *
   * 【改进】不改变任务状态为 'frontend_interrupted'，而是只标记中断类型
   * 这样 Worker 消息仍然会被处理，任务可以继续运行
   */
  markFrontendInterrupt(interruptType: InterruptType): void {
    if (this.currentTask && this.currentTask.status === 'running') {
      console.log('[TaskManager] 标记前端假中断:', {
        taskId: this.currentTask.id,
        interruptType,
        messageHandlersCount: this.messageHandlers.size,
        activeTaskIds: Array.from(this.activeTaskIds),
      })

      // 【改进】只标记中断类型和时间，不改变任务状态
      // 这样任务仍然被视为 'running'，Worker 消息仍然会被处理
      this.currentTask.interruptType = interruptType
      this.currentTask.interruptedAt = Date.now()
      this.currentTask.lastUpdatedAt = Date.now()

      // 持久化此状态
      this.persistTaskState(this.currentTask)
      this.notifySubscribers()

      console.log('[TaskManager] 前端假中断标记完成，任务仍在运行状态')
    }
  }

  /**
   * 标记任务为后端真中断
   * 当接收到来自 Worker 或后端的错误信号时调用
   */
  markBackendInterrupt(interruptType: InterruptType, errorMessage?: string): void {
    if (this.currentTask) {
      this.currentTask.status = 'failed'
      this.currentTask.interruptType = interruptType
      this.currentTask.interruptedAt = Date.now()
      this.currentTask.lastUpdatedAt = Date.now()
      if (errorMessage) {
        this.currentTask.error = errorMessage
      }
      // 持久化此状态
      this.persistTaskState(this.currentTask)
      this.notifySubscribers()
    }
  }

  /**
   * 判断中断类型是否为前端假中断
   */
  isFrontendInterrupt(interruptType?: InterruptType): boolean {
    if (!interruptType) return false
    return INTERRUPT_TYPE_TO_CATEGORY[interruptType] === INTERRUPT_TYPE_CATEGORIES.FRONTEND_INTERRUPT
  }

  /**
   * 判断中断类型是否为后端真中断
   */
  isBackendInterrupt(interruptType?: InterruptType): boolean {
    if (!interruptType) return false
    return INTERRUPT_TYPE_TO_CATEGORY[interruptType] === INTERRUPT_TYPE_CATEGORIES.BACKEND_INTERRUPT
  }

  /**
   * 获取当前任务状态
   * 【关键设计】返回当前任务状态的引用，页面可以读取但不能修改
   */
  getCurrentTask(): EnhancedTask | null {
    return this.currentTask
  }

  /**
   * 订阅任务状态变化
   * 返回取消订阅函数
   *
   * 【关键设计】
   * - 这是纯 JavaScript 的观察者模式
   * - 页面组件通过此方法订阅任务状态
   * - 当任务状态变化时，所有订阅者都会收到通知
   * - 页面卸载时，必须调用返回的取消订阅函数
   * - 即使页面卸载，TaskManager 的状态仍然存在
   * - 页面重新进入时，可以重新订阅获取最新状态
   */
  subscribeToTask(callback: (task: EnhancedTask | null) => void): () => void {
    this.subscribers.add(callback)

    // Return unsubscribe function
    return () => {
      this.subscribers.delete(callback)
    }
  }

  /**
   * 清除当前任务
   */
  clearTask(): void {
    this.currentTask = null
    this.clearPersistedTaskState()
    this.notifySubscribers()
  }

  /**
   * 销毁 TaskManager
   * 【注意】通常不需要调用此方法，除非在应用卸载时
   */
  destroy(): void {
    this.destroyWorker()
    this.currentTask = null
    this.subscribers.clear()
    console.log('[TaskManager] TaskManager 已销毁')
  }
}

// ============ 全局 TaskManager 实例导出 ============
/**
 * 【第五步】全局 TaskManager 实例
 * 所有页面和组件只能通过访问这个全局实例来读取任务状态或触发任务启动
 * 不允许在任何页面中创建新的 TaskManager 或 Worker
 */
export const taskManager = TaskManagerImpl.getInstance()
