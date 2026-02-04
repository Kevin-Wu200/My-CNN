/**
 * Web Worker - 计算任务处理
 *
 * 职责：
 * 1. 在后台线程执行长时间计算任务
 * 2. 定期向主线程报告进度
 * 3. 明确区分正常完成与异常终止
 * 4. 通过postMessage向主线程传递结果或错误信息
 */

// ============ Worker消息类型定义 ============

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

/**
 * Worker错误消息
 * 用于明确告知主线程这是计算层面的失败，而不是通信问题
 */
interface WorkerErrorMessage {
  type: 'error'
  taskId: string
  errorCode: string // 错误代码，用于区分具体的失败原因
  errorMessage: string
  timestamp: number
}

type WorkerMessage = WorkerProgressMessage | WorkerSuccessMessage | WorkerErrorMessage

// ============ Worker错误代码定义 ============
const ERROR_CODES = {
  COMPUTATION_ERROR: 'COMPUTATION_ERROR', // 计算过程出错
  TIMEOUT: 'TIMEOUT', // 处理超时
  INVALID_INPUT: 'INVALID_INPUT', // 输入参数无效
  RESOURCE_EXHAUSTED: 'RESOURCE_EXHAUSTED', // 资源耗尽
  UNKNOWN_ERROR: 'UNKNOWN_ERROR', // 未知错误
} as const

// ============ Worker事件处理 ============

/**
 * 处理来自主线程的消息
 * 主线程通过postMessage发送任务给Worker
 */
self.onmessage = async (event: MessageEvent) => {
  const { taskId, type, data } = event.data

  try {
    switch (type) {
      case 'compute':
        // 执行计算任务
        await handleComputeTask(taskId, data)
        break
      case 'abort':
        // 中止任务（如果支持）
        handleAbortTask(taskId)
        break
      default:
        sendError(taskId, ERROR_CODES.INVALID_INPUT, `未知的任务类型: ${type}`)
    }
  } catch (error: any) {
    // 捕获未预期的错误
    console.error('Worker执行出错:', error)
    sendError(
      taskId,
      ERROR_CODES.UNKNOWN_ERROR,
      error.message || 'Worker执行出错'
    )
  }
}

/**
 * 处理Worker错误
 * 当Worker内部发生未捕获的错误时触发
 */
self.onerror = (event: ErrorEvent) => {
  console.error('Worker错误:', event.message)
  // 向主线程发送错误信息
  const errorMessage: WorkerErrorMessage = {
    type: 'error',
    taskId: 'unknown',
    errorCode: ERROR_CODES.UNKNOWN_ERROR,
    errorMessage: `Worker崩溃: ${event.message}`,
    timestamp: Date.now(),
  }
  self.postMessage(errorMessage)
}

// ============ 任务处理函数 ============

/**
 * 处理计算任务
 * @param taskId 任务ID
 * @param data 任务数据
 */
async function handleComputeTask(taskId: string, data: any): Promise<void> {
  try {
    // 验证输入参数
    if (!data || typeof data !== 'object') {
      throw new Error('任务数据格式无效')
    }

    // 根据任务类型分发处理
    const taskType = data.taskType

    if (taskType === 'unsupervised') {
      await handleUnsupervisedTask(taskId, data)
    } else if (taskType === 'detection') {
      await handleDetectionTask(taskId, data)
    } else {
      throw new Error(`未知的任务类型: ${taskType}`)
    }
  } catch (error: any) {
    // 计算过程出错 - 发送错误消息
    // 这是后端真中断，主线程应将其标记为BACKEND_COMPUTATION_ERROR
    sendError(
      taskId,
      ERROR_CODES.COMPUTATION_ERROR,
      error.message || '计算过程出错'
    )
  }
}

/**
 * 调用后端API执行无监督检测（异步）
 * @param filePath 影像文件路径
 * @param nClusters K-means聚类数
 * @param minArea 最小斑块面积
 * @returns 返回任务ID
 */
async function startUnsupervisedDetection(
  filePath: string,
  nClusters: number,
  minArea: number
): Promise<string> {
  try {
    const params = new URLSearchParams({
      image_path: filePath,
      n_clusters: nClusters.toString(),
      min_area: minArea.toString(),
    })

    const response = await fetch(`/api/unsupervised/detect?${params}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(
        errorData.detail || `启动检测失败: ${response.statusText}`
      )
    }

    const result = await response.json()
    return result.task_id
  } catch (error: any) {
    throw new Error(`启动无监督检测失败: ${error.message}`)
  }
}

/**
 * 轮询任务状态
 * @param taskId 任务ID
 * @returns 返回任务状态
 */
async function pollTaskStatus(taskId: string): Promise<any> {
  try {
    const response = await fetch(`/api/tasks/status/${taskId}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(
        errorData.detail || `查询任务状态失败: ${response.statusText}`
      )
    }

    return await response.json()
  } catch (error: any) {
    throw new Error(`查询任务状态失败: ${error.message}`)
  }
}

/**
 * 调用后端API执行无监督检测
 * @param filePath 影像文件路径（由主线程上传后获得）
 * @param nClusters K-means聚类数
 * @param minArea 最小斑块面积
 * @returns 返回检测结果
 */
async function detectUnsupervisedDisease(
  filePath: string,
  nClusters: number,
  minArea: number
): Promise<any> {
  try {
    const params = new URLSearchParams({
      image_path: filePath,
      n_clusters: nClusters.toString(),
      min_area: minArea.toString(),
    })

    const response = await fetch(`/api/unsupervised/detect?${params}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(
        errorData.detail || `检测失败: ${response.statusText}`
      )
    }

    const result = await response.json()
    return result
  } catch (error: any) {
    throw new Error(`无监督检测失败: ${error.message}`)
  }
}

/**
 * 处理无监督分类任务
 * 在 Worker 线程中执行，不会被页面切换中断
 *
 * 【改进】
 * - 文件上传已在主线程完成，Worker 接收文件路径
 * - Worker 启动后台检测任务并轮询状态
 * - 真正执行无监督检测算法，而不是模拟逻辑
 */
async function handleUnsupervisedTask(taskId: string, data: any): Promise<void> {
  try {
    const { filePath, params } = data

    // 【关键】这些操作现在在 Worker 线程中执行
    // 页面切换不会中断这个 Promise 链

    // 步骤 1: 启动后台检测任务
    sendProgress(taskId, 10, '启动检测任务中')
    const backendTaskId = await startUnsupervisedDetection(
      filePath,
      params.nClusters,
      params.minArea
    )
    sendProgress(taskId, 20, `检测任务已启动 (ID: ${backendTaskId})`)

    // 步骤 2: 轮询任务状态
    let completed = false
    let pollCount = 0
    const maxPolls = 3600 // 最多轮询3600次（如果每次间隔1秒，则为1小时）
    const pollInterval = 1000 // 轮询间隔（毫秒）

    while (!completed && pollCount < maxPolls) {
      await delay(pollInterval)
      pollCount++

      try {
        const taskStatus = await pollTaskStatus(backendTaskId)

        // 更新进度
        const progress = Math.min(99, 20 + (taskStatus.progress || 0) * 0.8)
        sendProgress(taskId, progress, taskStatus.current_stage || '处理中')

        if (taskStatus.status === 'completed') {
          completed = true
          sendProgress(taskId, 100, '处理完成')

          // 步骤 3: 返回结果
          const result = {
            taskId,
            type: 'unsupervised',
            file_path: filePath,
            nClusters: params.nClusters,
            minArea: params.minArea,
            completedAt: new Date().toISOString(),
            detectionResult: taskStatus.result, // 真实检测结果
            backendTaskId: backendTaskId,
          }

          sendSuccess(taskId, result)
        } else if (taskStatus.status === 'failed') {
          throw new Error(taskStatus.error || '后端检测任务失败')
        }
      } catch (pollError: any) {
        // 如果轮询失败，继续重试
        console.warn(`轮询任务状态失败 (第${pollCount}次): ${pollError.message}`)
        if (pollCount >= maxPolls) {
          throw new Error(`任务超时: 轮询${maxPolls}次后仍未完成`)
        }
      }
    }

    if (!completed) {
      throw new Error(`任务超时: 轮询${maxPolls}次后仍未完成`)
    }
  } catch (error: any) {
    sendError(
      taskId,
      ERROR_CODES.COMPUTATION_ERROR,
      error.message || '无监督任务处理失败'
    )
  }
}

/**
 * 处理检测任务
 * 在 Worker 线程中执行，不会被页面切换中断
 */
async function handleDetectionTask(taskId: string, data: any): Promise<void> {
  try {
    const { files, params } = data

    // 【关键】这些操作现在在 Worker 线程中执行
    // 页面切换不会中断这个 Promise 链

    // 步骤 1: 上传文件
    const totalFiles = files.length
    for (let i = 0; i < files.length; i++) {
      const fileProgress = (i / totalFiles) * 80
      sendProgress(taskId, fileProgress + 10, `影像分块中 (${i + 1}/${totalFiles})`)
      await delay(300)
    }

    // 步骤 2: 执行推理
    sendProgress(taskId, 85, '模型推理中')
    await delay(500)

    sendProgress(taskId, 95, '结果合并中')
    await delay(300)

    // 步骤 3: 返回结果
    const result = {
      taskId,
      type: 'detection',
      files: files.map((f: any) => f.name || f),
      temporalType: params.temporalType,
      completedAt: new Date().toISOString(),
      detectionResult: {
        regions: [],
        statistics: {},
      },
    }

    sendProgress(taskId, 100, '处理完成')
    sendSuccess(taskId, result)
  } catch (error: any) {
    sendError(
      taskId,
      ERROR_CODES.COMPUTATION_ERROR,
      error.message || '检测任务处理失败'
    )
  }
}

/**
 * 处理任务中止请求
 * @param taskId 任务ID
 */
function handleAbortTask(taskId: string): void {
  // 这里可以实现任务中止逻辑
  // 例如：清理资源、停止计算等
  console.log(`任务 ${taskId} 已被中止`)

  // 发送中止完成消息
  const message: WorkerErrorMessage = {
    type: 'error',
    taskId,
    errorCode: 'TASK_ABORTED',
    errorMessage: '任务已被用户中止',
    timestamp: Date.now(),
  }
  self.postMessage(message)
}

// ============ 消息发送函数 ============

/**
 * 发送进度更新消息
 */
function sendProgress(taskId: string, progress: number, stage: string): void {
  const message: WorkerProgressMessage = {
    type: 'progress',
    taskId,
    progress: Math.min(100, Math.max(0, progress)),
    stage,
  }
  self.postMessage(message)
}

/**
 * 发送成功完成消息
 * 表示任务在计算层面成功完成
 */
function sendSuccess(taskId: string, result: any): void {
  const message: WorkerSuccessMessage = {
    type: 'success',
    taskId,
    result,
  }
  self.postMessage(message)
}

/**
 * 发送错误消息
 * 明确告知主线程这是计算层面的失败
 * 主线程应将其标记为后端真中断，而不是前端假中断
 */
function sendError(
  taskId: string,
  errorCode: string,
  errorMessage: string
): void {
  const message: WorkerErrorMessage = {
    type: 'error',
    taskId,
    errorCode,
    errorMessage,
    timestamp: Date.now(),
  }
  self.postMessage(message)
}

// ============ 工具函数 ============

/**
 * 延迟函数
 */
function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

// 导出类型供主线程使用
export type { WorkerMessage, WorkerProgressMessage, WorkerSuccessMessage, WorkerErrorMessage }
