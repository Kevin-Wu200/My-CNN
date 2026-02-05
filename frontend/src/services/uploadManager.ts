/**
 * 上传管理器 - 主线程与 uploadWorker 的通信桥梁
 *
 * 职责：
 * 1. 初始化和管理 uploadWorker
 * 2. 启动文件上传任务
 * 3. 监听上传进度和完成事件
 * 4. 提供上传状态查询接口
 * 5. 轮询后端上传状态
 */

interface UploadProgressCallback {
  (progress: number, uploadedChunks: number, totalChunks: number): void
}

interface UploadCompleteCallback {
  (result: { filePath: string; fileName: string; fileSize: number; totalChunks: number }): void
}

interface UploadErrorCallback {
  (error: { code: string; message: string; failedChunkIndex?: number }): void
}

interface UploadCallbacks {
  onProgress?: UploadProgressCallback
  onComplete?: UploadCompleteCallback
  onError?: UploadErrorCallback
}

interface UploadSession {
  uploadId: string
  fileName: string
  fileSize: number
  status: 'uploading' | 'completed' | 'failed'
  progress: number
  uploadedChunks: number
  totalChunks: number
  callbacks: UploadCallbacks
  pollInterval?: NodeJS.Timeout
}

class UploadManager {
  private worker: Worker | null = null
  private sessions = new Map<string, UploadSession>()
  private static instance: UploadManager

  private constructor() {
    this.initializeWorker()
  }

  static getInstance(): UploadManager {
    if (!UploadManager.instance) {
      UploadManager.instance = new UploadManager()
    }
    return UploadManager.instance
  }

  /**
   * 初始化 uploadWorker
   */
  private initializeWorker() {
    try {
      // 使用 new Worker 创建 uploadWorker
      // 注意：需要在 vite.config.ts 中配置 worker 支持
      this.worker = new Worker(new URL('./uploadWorker.ts', import.meta.url), { type: 'module' })

      this.worker.onmessage = (event: MessageEvent) => {
        this.handleWorkerMessage(event.data)
      }

      this.worker.onerror = (error: ErrorEvent) => {
        console.error('[UploadManager] Worker 错误:', error.message)
      }

      console.log('[UploadManager] uploadWorker 初始化成功')
    } catch (error) {
      console.error('[UploadManager] uploadWorker 初始化失败:', error)
    }
  }

  /**
   * 处理 Worker 消息
   */
  private handleWorkerMessage(message: any) {
    const { type, uploadId } = message
    const session = this.sessions.get(uploadId)

    if (!session) {
      console.warn(`[UploadManager] 未找到上传会话: ${uploadId}`)
      return
    }

    switch (type) {
      case 'progress':
        this.handleProgress(session, message)
        break
      case 'success':
        this.handleSuccess(session, message)
        break
      case 'error':
        this.handleError(session, message)
        break
    }
  }

  /**
   * 处理进度更新
   */
  private handleProgress(session: UploadSession, message: any) {
    session.progress = message.progress
    session.uploadedChunks = message.uploadedChunks
    session.totalChunks = message.totalChunks

    console.log(`[UploadManager] 上传进度 [${session.uploadId}]:`, {
      progress: session.progress,
      uploadedChunks: session.uploadedChunks,
      totalChunks: session.totalChunks,
    })

    session.callbacks.onProgress?.(session.progress, session.uploadedChunks, session.totalChunks)
  }

  /**
   * 处理上传成功
   */
  private handleSuccess(session: UploadSession, message: any) {
    session.status = 'completed'
    session.progress = 100

    console.log(`[UploadManager] 分片上传完成 [${session.uploadId}]:`, message.result)

    // 停止轮询
    if (session.pollInterval) {
      clearInterval(session.pollInterval)
      session.pollInterval = undefined
    }

    // 调用完成回调
    session.callbacks.onComplete?.(message.result)

    // 延迟清理会话
    setTimeout(() => {
      this.sessions.delete(session.uploadId)
    }, 1000)
  }

  /**
   * 处理上传错误
   */
  private handleError(session: UploadSession, message: any) {
    session.status = 'failed'

    console.error(`[UploadManager] 上传失败 [${session.uploadId}]:`, {
      errorCode: message.errorCode,
      errorMessage: message.errorMessage,
      failedChunkIndex: message.failedChunkIndex,
    })

    // 停止轮询
    if (session.pollInterval) {
      clearInterval(session.pollInterval)
      session.pollInterval = undefined
    }

    session.callbacks.onError?.({
      code: message.errorCode,
      message: message.errorMessage,
      failedChunkIndex: message.failedChunkIndex,
    })

    this.sessions.delete(session.uploadId)
  }

  /**
   * 启动文件上传
   */
  async uploadFile(file: File, callbacks: UploadCallbacks): Promise<string> {
    if (!this.worker) {
      throw new Error('uploadWorker 未初始化')
    }

    const uploadId = this.generateUploadId()

    const session: UploadSession = {
      uploadId,
      fileName: file.name,
      fileSize: file.size,
      status: 'uploading',
      progress: 0,
      uploadedChunks: 0,
      totalChunks: 0,
      callbacks,
    }

    this.sessions.set(uploadId, session)

    console.log('[UploadManager] 启动文件上传:', {
      uploadId,
      fileName: file.name,
      fileSize: file.size,
    })

    // 发送上传任务到 Worker
    this.worker.postMessage({
      uploadId,
      type: 'upload',
      data: { file },
    })

    // 启动后端状态轮询（每 5 秒查询一次）
    this.startStatusPolling(uploadId)

    return uploadId
  }

  /**
   * 启动后端状态轮询
   */
  private startStatusPolling(uploadId: string) {
    const session = this.sessions.get(uploadId)
    if (!session) return

    console.log(`[UploadManager] 启动后端状态轮询 [${uploadId}]`)

    let consecutiveErrors = 0
    const MAX_CONSECUTIVE_ERRORS = 3

    session.pollInterval = setInterval(async () => {
      try {
        const response = await fetch(`/api/upload/status/${uploadId}`)
        if (!response.ok) {
          consecutiveErrors++
          console.warn(`[UploadManager] 查询状态失败: ${response.status} (连续错误: ${consecutiveErrors})`)

          // 连续错误超过阈值，停止轮询
          if (consecutiveErrors >= MAX_CONSECUTIVE_ERRORS) {
            console.error(`[UploadManager] 后端不可达，停止轮询 [${uploadId}]`)
            if (session.pollInterval) {
              clearInterval(session.pollInterval)
              session.pollInterval = undefined
            }
            session.status = 'failed'
            session.callbacks.onError?.({
              code: 'BACKEND_UNREACHABLE',
              message: '后端服务不可达，上传已中止',
            })
            this.sessions.delete(uploadId)
          }
          return
        }

        // 成功响应，重置错误计数
        consecutiveErrors = 0

        const status = await response.json()

        console.log(`[UploadManager] 后端状态 [${uploadId}]:`, {
          status: status.status,
          progress: status.progress,
          uploadedChunks: status.uploadedChunks,
          totalChunks: status.totalChunks,
        })

        // 更新会话状态
        session.progress = status.progress
        session.uploadedChunks = status.uploadedChunks
        session.totalChunks = status.totalChunks

        // 如果后端状态为 completed，调用完成回调
        if (status.status === 'completed' && status.filePath) {
          console.log(`[UploadManager] 后端合并完成 [${uploadId}]:`, status.filePath)

          if (session.pollInterval) {
            clearInterval(session.pollInterval)
            session.pollInterval = undefined
          }

          session.status = 'completed'
          session.callbacks.onComplete?.({
            filePath: status.filePath,
            fileName: session.fileName,
            fileSize: session.fileSize,
            totalChunks: session.totalChunks,
          })

          this.sessions.delete(uploadId)
        }
        // 如果后端状态为 failed，调用错误回调
        else if (status.status === 'failed') {
          console.error(`[UploadManager] 后端合并失败 [${uploadId}]:`, status.errorMessage)

          if (session.pollInterval) {
            clearInterval(session.pollInterval)
            session.pollInterval = undefined
          }

          session.status = 'failed'
          session.callbacks.onError?.({
            code: 'BACKEND_MERGE_FAILED',
            message: status.errorMessage || '后端合并失败',
          })

          this.sessions.delete(uploadId)
        }
      } catch (error) {
        consecutiveErrors++
        console.error(`[UploadManager] 轮询状态异常 [${uploadId}]:`, error, `(连续错误: ${consecutiveErrors})`)

        // 连续错误超过阈值，停止轮询
        if (consecutiveErrors >= MAX_CONSECUTIVE_ERRORS) {
          console.error(`[UploadManager] 轮询异常过多，停止轮询 [${uploadId}]`)
          if (session.pollInterval) {
            clearInterval(session.pollInterval)
            session.pollInterval = undefined
          }
          session.status = 'failed'
          session.callbacks.onError?.({
            code: 'POLLING_ERROR',
            message: '轮询异常，上传已中止',
          })
          this.sessions.delete(uploadId)
        }
      }
    }, 5000)
  }

  /**
   * 获取上传会话状态
   */
  getSession(uploadId: string): UploadSession | undefined {
    return this.sessions.get(uploadId)
  }

  /**
   * 生成上传 ID
   */
  private generateUploadId(): string {
    return `upload_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  }

  /**
   * 销毁 Worker
   */
  destroy() {
    if (this.worker) {
      this.worker.terminate()
      this.worker = null
    }
    // 清理所有轮询
    this.sessions.forEach((session) => {
      if (session.pollInterval) {
        clearInterval(session.pollInterval)
      }
    })
    this.sessions.clear()
  }
}

export const uploadManager = UploadManager.getInstance()

