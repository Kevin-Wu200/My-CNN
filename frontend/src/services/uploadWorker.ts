/**
 * Web Worker - 文件分片上传处理
 *
 * 职责：
 * 1. 将文件分片（5MB/片）
 * 2. 并发上传多个分片（最大4个）
 * 3. 单个分片失败重试1次
 * 4. 向主线程报告上传进度
 * 5. 处理上传错误和超时
 */

// ============ 上传消息类型定义 ============

interface UploadProgressMessage {
  type: 'progress'
  uploadId: string
  uploadedChunks: number
  totalChunks: number
  progress: number
}

interface UploadSuccessMessage {
  type: 'success'
  uploadId: string
  result: {
    filePath: string
    fileName: string
    fileSize: number
    totalChunks: number
  }
}

interface UploadErrorMessage {
  type: 'error'
  uploadId: string
  errorCode: string
  errorMessage: string
  failedChunkIndex?: number
}

type UploadMessage = UploadProgressMessage | UploadSuccessMessage | UploadErrorMessage

// ============ 上传错误代码 ============

const UPLOAD_ERROR_CODES = {
  CHUNK_UPLOAD_FAILED: 'CHUNK_UPLOAD_FAILED',
  CHUNK_RETRY_EXHAUSTED: 'CHUNK_RETRY_EXHAUSTED',
  INVALID_INPUT: 'INVALID_INPUT',
  NETWORK_ERROR: 'NETWORK_ERROR',
  UNKNOWN_ERROR: 'UNKNOWN_ERROR',
  RATE_LIMITED: 'RATE_LIMITED',
} as const

// ============ 常量配置 ============

const CHUNK_SIZE = 5 * 1024 * 1024 // 5MB
const MAX_CONCURRENT_UPLOADS = 2 // 降低并发数，从4降至2
const CHUNK_RETRY_COUNT = 3 // 增加重试次数
const CHUNK_UPLOAD_TIMEOUT = 60000 // 60秒
const RATE_LIMIT_BACKOFF_BASE = 1000 // 基础退避时间（毫秒）
const RATE_LIMIT_BACKOFF_MAX = 30000 // 最大退避时间（毫秒）

// ============ 上传任务状态 ============

interface UploadTask {
  uploadId: string
  file: File
  chunks: Blob[]
  totalChunks: number
  uploadedChunks: number
  uploadedChunkIndexes: Set<number>
  failedChunks: Set<number>
  uploadingChunks: Set<number>
  chunkRetries: Map<number, number>
  rateLimitedChunks: Set<number> // 被限流的分片
  chunkBackoffTimes: Map<number, number> // 分片的退避时间
  globalBackoffUntil: number // 全局退避截止时间
}

const uploadTasks = new Map<string, UploadTask>()

// ============ 辅助函数 ============

/**
 * 将文件分片
 */
function sliceFile(file: File, chunkSize: number): Blob[] {
  const chunks: Blob[] = []
  let offset = 0

  while (offset < file.size) {
    const end = Math.min(offset + chunkSize, file.size)
    chunks.push(file.slice(offset, end))
    offset = end
  }

  return chunks
}

/**
 * 发送进度消息
 */
function sendProgress(uploadId: string, uploadedChunks: number, totalChunks: number) {
  const progress = Math.round((uploadedChunks / totalChunks) * 100)
  const message: UploadProgressMessage = {
    type: 'progress',
    uploadId,
    uploadedChunks,
    totalChunks,
    progress,
  }
  self.postMessage(message)
}

/**
 * 发送成功消息
 */
function sendSuccess(uploadId: string, filePath: string, fileName: string, fileSize: number, totalChunks: number) {
  const message: UploadSuccessMessage = {
    type: 'success',
    uploadId,
    result: {
      filePath,
      fileName,
      fileSize,
      totalChunks,
    },
  }
  self.postMessage(message)
}

/**
 * 发送错误消息
 */
function sendError(uploadId: string, errorCode: string, errorMessage: string, failedChunkIndex?: number) {
  const message: UploadErrorMessage = {
    type: 'error',
    uploadId,
    errorCode,
    errorMessage,
    failedChunkIndex,
  }
  self.postMessage(message)
}

/**
 * 上传单个分片
 */
async function uploadChunk(
  uploadId: string,
  chunkIndex: number,
  chunk: Blob,
  fileName: string,
  fileSize: number,
  totalChunks: number
): Promise<boolean> {
  const formData = new FormData()
  formData.append('chunk', chunk)
  formData.append('chunkIndex', chunkIndex.toString())
  formData.append('totalChunks', totalChunks.toString())
  formData.append('fileName', fileName)
  formData.append('fileSize', fileSize.toString())
  formData.append('uploadId', uploadId)

  try {
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), CHUNK_UPLOAD_TIMEOUT)

    const response = await fetch('/api/upload/chunk', {
      method: 'POST',
      body: formData,
      signal: controller.signal,
    })

    clearTimeout(timeoutId)

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))

      // 处理 429 Too Many Requests 错误
      if (response.status === 429) {
        const error = new Error(errorData.detail || '请求过于频繁')
        (error as any).statusCode = 429
        throw error
      }

      throw new Error(errorData.detail || `分片上传失败: ${response.statusText}`)
    }

    return true
  } catch (error: any) {
    console.error(`[UploadWorker] 分片 ${chunkIndex} 上传失败:`, error.message)
    throw error
  }
}

/**
 * 处理分片上传队列（并发控制 + 退避策略）
 */
async function processUploadQueue(uploadId: string) {
  const task = uploadTasks.get(uploadId)
  if (!task) return

  // 检查全局退避是否仍在进行
  if (task.globalBackoffUntil > Date.now()) {
    // 仍在退避期间，延迟后重新尝试
    setTimeout(() => processUploadQueue(uploadId), 500)
    return
  }

  const queue: number[] = []
  for (let i = 0; i < task.totalChunks; i++) {
    if (!task.failedChunks.has(i) && !task.uploadingChunks.has(i) && !task.uploadedChunkIndexes.has(i)) {
      // 检查该分片是否在个别退避期间
      const backoffUntil = task.chunkBackoffTimes.get(i) || 0
      if (backoffUntil <= Date.now()) {
        queue.push(i)
      }
    }
  }

  while (queue.length > 0 && task.uploadingChunks.size < MAX_CONCURRENT_UPLOADS) {
    const chunkIndex = queue.shift()!
    task.uploadingChunks.add(chunkIndex)

    // 异步上传，不等待
    uploadChunkWithRetry(uploadId, chunkIndex)
      .then(() => {
        task.uploadingChunks.delete(chunkIndex)
        if (!task.uploadedChunkIndexes.has(chunkIndex)) {
          task.uploadedChunkIndexes.add(chunkIndex)
          task.uploadedChunks = task.uploadedChunkIndexes.size
          sendProgress(uploadId, task.uploadedChunks, task.totalChunks)
        }

        // 继续处理队列
        processUploadQueue(uploadId)

        // 检查是否全部完成
        if (task.uploadedChunks === task.totalChunks) {
          completeUpload(uploadId)
        }
      })
      .catch((error) => {
        task.uploadingChunks.delete(chunkIndex)

        // 检查是否是速率限制错误
        if ((error as any).statusCode === 429) {
          task.rateLimitedChunks.add(chunkIndex)
          // 计算退避时间（指数退避）
          const retries = task.chunkRetries.get(chunkIndex) || 0
          const backoffTime = Math.min(
            RATE_LIMIT_BACKOFF_BASE * Math.pow(2, retries),
            RATE_LIMIT_BACKOFF_MAX
          )
          task.chunkBackoffTimes.set(chunkIndex, Date.now() + backoffTime)
          console.warn(`[UploadWorker] 分片 ${chunkIndex} 被限流，${backoffTime}ms 后重试`)

          // 设置全局退避，暂停所有上传
          task.globalBackoffUntil = Date.now() + backoffTime
          task.chunkRetries.set(chunkIndex, retries + 1)

          // 延迟后继续处理队列
          setTimeout(() => processUploadQueue(uploadId), backoffTime + 100)
        } else {
          // 非速率限制错误，标记为失败
          task.failedChunks.add(chunkIndex)
          sendError(uploadId, UPLOAD_ERROR_CODES.CHUNK_RETRY_EXHAUSTED, error.message, chunkIndex)

          // 如果失败分片过多（超过50%），中止上传
          const failureRate = task.failedChunks.size / task.totalChunks
          if (failureRate > 0.5) {
            sendError(uploadId, UPLOAD_ERROR_CODES.CHUNK_UPLOAD_FAILED, `上传失败率过高 (${Math.round(failureRate * 100)}%)，已中止上传`)
            uploadTasks.delete(uploadId)
          } else {
            // 继续处理队列中的其他分片
            processUploadQueue(uploadId)
          }
        }
      })
  }
}

/**
 * 上传分片（带重试）
 */
async function uploadChunkWithRetry(uploadId: string, chunkIndex: number) {
  const task = uploadTasks.get(uploadId)
  if (!task) throw new Error('上传任务不存在')

  const retries = task.chunkRetries.get(chunkIndex) || 0
  const chunk = task.chunks[chunkIndex]

  try {
    await uploadChunk(uploadId, chunkIndex, chunk, task.file.name, task.file.size, task.totalChunks)
  } catch (error: any) {
    // 速率限制错误直接抛出，由 processUploadQueue 处理
    if ((error as any).statusCode === 429) {
      throw error
    }

    // 其他错误进行重试
    if (retries < CHUNK_RETRY_COUNT) {
      task.chunkRetries.set(chunkIndex, retries + 1)
      // 延迟后重试
      await new Promise(resolve => setTimeout(resolve, 500))
      return uploadChunkWithRetry(uploadId, chunkIndex)
    } else {
      // 重试次数已用尽
      throw new Error(`分片 ${chunkIndex} 上传失败（已重试 ${CHUNK_RETRY_COUNT} 次）: ${error.message}`)
    }
  }
}

/**
 * 轮询查询上传状态直到获得 filePath
 * 第九步：前端禁止在 filePath 未返回前发起任何文件就绪检查或检测请求
 */
async function pollUploadStatus(uploadId: string, maxRetries: number = 120, retryInterval: number = 1000): Promise<string> {
  let retries = 0

  while (retries < maxRetries) {
    try {
      const response = await fetch(`/api/upload/status/${uploadId}`)

      if (!response.ok) {
        throw new Error(`查询状态失败: ${response.statusText}`)
      }

      const statusData = await response.json()

      // 检查状态是否为 completed
      if (statusData.status === 'completed' && statusData.filePath) {
        console.log(`[UploadWorker] 上传完成，获得 filePath: ${statusData.filePath}`)
        return statusData.filePath
      }

      // 检查是否失败
      if (statusData.status === 'failed') {
        throw new Error(`上传失败: ${statusData.errorMessage || '未知错误'}`)
      }

      // 继续轮询
      retries++
      await new Promise(resolve => setTimeout(resolve, retryInterval))
    } catch (error: any) {
      console.error(`[UploadWorker] 查询状态异常 (重试 ${retries}/${maxRetries}):`, error.message)
      retries++
      await new Promise(resolve => setTimeout(resolve, retryInterval))
    }
  }

  throw new Error(`轮询超时：无法获得 filePath (已重试 ${maxRetries} 次)`)
}

/**
 * 完成上传
 */
async function completeUpload(uploadId: string) {
  const task = uploadTasks.get(uploadId)
  if (!task) return

  try {
    const response = await fetch('/api/upload/complete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        uploadId,
        fileName: task.file.name,
        fileSize: task.file.size,
        totalChunks: task.totalChunks,
      }),
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || `上传完成失败: ${response.statusText}`)
    }

    // 第九步：前端禁止在 filePath 未返回前发起任何文件就绪检查或检测请求
    // 轮询查询上传状态直到获得 filePath
    console.log(`[UploadWorker] 开始轮询查询上传状态: ${uploadId}`)
    const filePath = await pollUploadStatus(uploadId)

    sendSuccess(uploadId, filePath, task.file.name, task.file.size, task.totalChunks)
    uploadTasks.delete(uploadId)
  } catch (error: any) {
    sendError(uploadId, UPLOAD_ERROR_CODES.UNKNOWN_ERROR, `上传完成失败: ${error.message}`)
    uploadTasks.delete(uploadId)
  }
}

// ============ Worker 事件处理 ============

/**
 * 处理来自主线程的消息
 */
self.onmessage = async (event: MessageEvent) => {
  const { uploadId, type, data } = event.data

  try {
    switch (type) {
      case 'upload':
        // 启动文件上传
        await handleUpload(uploadId, data)
        break
      default:
        sendError(uploadId, UPLOAD_ERROR_CODES.INVALID_INPUT, `未知的操作类型: ${type}`)
    }
  } catch (error: any) {
    console.error('[UploadWorker] 执行出错:', error)
    sendError(uploadId, UPLOAD_ERROR_CODES.UNKNOWN_ERROR, error.message || 'Worker 执行出错')
  }
}

/**
 * 处理上传请求
 */
async function handleUpload(uploadId: string, data: any) {
  const { file } = data

  if (!file || !(file instanceof Blob)) {
    throw new Error('无效的文件对象')
  }

  // 分片文件
  const chunks = sliceFile(file as File, CHUNK_SIZE)
  const totalChunks = chunks.length

  // 创建上传任务
  const task: UploadTask = {
    uploadId,
    file: file as File,
    chunks,
    totalChunks,
    uploadedChunks: 0,
    uploadedChunkIndexes: new Set(),
    failedChunks: new Set(),
    uploadingChunks: new Set(),
    chunkRetries: new Map(),
    rateLimitedChunks: new Set(),
    chunkBackoffTimes: new Map(),
    globalBackoffUntil: 0,
  }

  uploadTasks.set(uploadId, task)

  // 发送初始进度
  sendProgress(uploadId, 0, totalChunks)

  // 开始处理上传队列
  processUploadQueue(uploadId)
}

/**
 * Worker 错误处理
 */
self.onerror = (event: ErrorEvent) => {
  console.error('[UploadWorker] Worker 崩溃:', event.message)
  const errorMessage: UploadErrorMessage = {
    type: 'error',
    uploadId: 'unknown',
    errorCode: UPLOAD_ERROR_CODES.UNKNOWN_ERROR,
    errorMessage: `Worker 崩溃: ${event.message}`,
  }
  self.postMessage(errorMessage)
}
