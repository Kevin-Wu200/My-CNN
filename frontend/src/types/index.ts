export interface ApiResponse<T = any> {
  code: number
  message: string
  data?: T
}

export interface TrainingTask {
  id: string
  name: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  createdAt: string
  updatedAt: string
}

export interface DetectionTask {
  id: string
  name: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  createdAt: string
  updatedAt: string
}

export interface DetectionPoint {
  id: string
  x: number
  y: number
  confidence: number
}

export interface ModelConfig {
  cnnBackbone: string
  temporalModule: string
  inputType: string
  advancedParams?: Record<string, any>
}

// ============ 增强的任务状态定义 ============
// 包含中断类型区分逻辑，用于区分前端假中断与后端真中断

export type InterruptType =
  // 前端假中断
  | 'frontend_page_refresh'
  | 'frontend_route_change'
  | 'frontend_component_unmount'
  | 'frontend_connection_lost'
  // 后端真中断
  | 'backend_computation_error'
  | 'backend_worker_crash'
  | 'backend_inference_failed'
  | 'backend_timeout'
  | 'backend_manual_abort'

export type TaskStatus = 'idle' | 'running' | 'completed' | 'failed' | 'frontend_interrupted'

/**
 * 增强的任务状态数据结构
 * 包含中断来源字段，用于区分前端假中断与后端真中断
 */
export interface EnhancedTask {
  // 任务唯一标识
  id: string
  // 任务类型
  type: 'unsupervised' | 'detection'
  // 运行状态
  status: TaskStatus
  // 进度百分比 (0-100)
  progress: number
  // 当前阶段提示
  currentStage: string
  // 任务创建时间戳
  createdAt: number
  // 最后一次更新时间戳
  lastUpdatedAt: number
  // 任务结果
  result?: any
  // 错误信息
  error?: string
  // ============ 中断来源字段 ============
  // 用于区分前端假中断与后端真中断
  // 当status为'failed'或'frontend_interrupted'时，此字段指示中断原因
  interruptType?: InterruptType
  // 中断发生的时间戳
  interruptedAt?: number
  // ============ Worker 实例追踪 ============
  // 用于追踪任务所属的 Worker 实例
  workerInstanceId?: string
}

/**
 * 任务持久化存储结构
 * 用于页面刷新后恢复任务状态
 */
export interface PersistedTaskState {
  // 任务基本信息
  taskId: string
  taskType: 'unsupervised' | 'detection'
  // 任务状态
  status: TaskStatus
  progress: number
  currentStage: string
  // 时间信息
  createdAt: number
  lastUpdatedAt: number
  // 中断信息
  interruptType?: InterruptType
  interruptedAt?: number
  // 用于判断是否为前端假中断的标记
  workerInstanceId?: string
}
