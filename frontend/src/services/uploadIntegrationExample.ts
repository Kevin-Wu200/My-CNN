/**
 * 分片上传集成示例
 *
 * 展示如何在 TaskManager 中使用 uploadManager 进行分片上传
 * 以及如何在 Vue 组件中调用 TaskManager 启动上传任务
 */

// ============ 示例 1: 在 Vue 组件中启动非监督检测任务 ============

import { taskManager } from '@/services/taskManager'

export default {
  methods: {
    async handleUnsupervisedDetection() {
      const file = this.selectedFile // File 对象

      try {
        // 启动非监督检测任务
        // TaskManager 内部会自动使用 uploadManager 进行分片上传
        const taskId = await taskManager.startUnsupervisedTask(file, {
          nClusters: 4,
          minArea: 50,
        })

        console.log('任务已启动:', taskId)

        // 订阅任务状态变化
        const unsubscribe = taskManager.subscribeToTask((task) => {
          if (task) {
            console.log('任务进度:', {
              progress: task.progress,
              stage: task.currentStage,
              status: task.status,
            })

            // 任务完成或失败时取消订阅
            if (task.status === 'completed' || task.status === 'failed') {
              unsubscribe()
            }
          }
        })

        // 跳转到任务进度页面
        this.$router.push('/task-progress')
      } catch (error) {
        console.error('任务启动失败:', error.message)
      }
    },
  },
}

// ============ 示例 2: 在 Vue 组件中启动检测任务（多文件） ============

export default {
  methods: {
    async handleDetection() {
      const files = this.selectedFiles // File[] 数组

      try {
        // 启动检测任务
        // TaskManager 内部会自动对每个文件进行分片上传
        const taskId = await taskManager.startDetectionTask(files, {
          temporalType: 'single',
        })

        console.log('检测任务已启动:', taskId)

        // 跳转到任务进度页面
        this.$router.push('/task-progress')
      } catch (error) {
        console.error('检测任务启动失败:', error.message)
      }
    },
  },
}

// ============ 示例 3: 直接使用 uploadManager 进行分片上传 ============

import { uploadManager } from '@/services/uploadManager'

async function uploadLargeFile(file: File) {
  try {
    const uploadId = await uploadManager.uploadFile(file, {
      onProgress: (progress, uploadedChunks, totalChunks) => {
        console.log(`上传进度: ${progress}% (${uploadedChunks}/${totalChunks})`)
      },
      onComplete: (result) => {
        console.log('上传完成:', result)
        // 使用 result.filePath 进行后续操作
      },
      onError: (error) => {
        console.error('上传失败:', error.message)
      },
    })

    console.log('上传已启动:', uploadId)
  } catch (error) {
    console.error('上传启动失败:', error.message)
  }
}

// ============ 示例 4: 后端接收分片上传的处理流程 ============

/**
 * 后端处理流程：
 *
 * 1. 前端分片上传
 *    - uploadWorker 将文件分成 5MB 的分片
 *    - 最多 4 个分片并发上传
 *    - 每个分片失败自动重试 1 次
 *
 * 2. 后端接收分片
 *    POST /api/upload/chunk
 *    - 保存分片到临时目录 (TEMP_DIR/uploadId/chunk_0, chunk_1, ...)
 *    - 返回上传成功响应
 *
 * 3. 前端完成上传
 *    POST /api/upload/complete
 *    - 通知后端所有分片已上传
 *
 * 4. 后端合并分片
 *    - 按顺序读取所有分片文件
 *    - 合并为完整文件
 *    - 验证文件大小
 *    - 保存到最终目录 (DETECTION_IMAGES_DIR)
 *    - 清理临时文件
 *    - 返回最终文件路径
 *
 * 5. TaskManager 继续处理
 *    - 使用文件路径启动 Worker 计算任务
 *    - Worker 读取文件进行检测
 */

// ============ 示例 5: 进度计算方式 ============

/**
 * 上传进度计算：
 *
 * 总进度 = (已成功上传的分片数 / 总分片数) × 100%
 *
 * 例如：
 * - 文件大小: 100MB
 * - 分片大小: 5MB
 * - 总分片数: 20
 * - 已上传: 12 个分片
 * - 进度: (12 / 20) × 100% = 60%
 *
 * 注意：
 * - 不使用 XMLHttpRequest.onprogress（不准确）
 * - 不使用 fetch 流式进度（不准确）
 * - 只基于"已成功上传的分片数"计算
 * - 每个分片成功后立即更新进度
 */

// ============ 示例 6: 错误处理和重试 ============

/**
 * 错误处理策略：
 *
 * 1. 单个分片上传失败
 *    - 自动重试 1 次
 *    - 如果重试仍失败，则终止整个上传
 *    - 返回错误信息和失败的分片索引
 *
 * 2. 网络超时
 *    - 单个分片上传超时: 60 秒
 *    - 超时后自动重试
 *    - 重试仍超时则失败
 *
 * 3. 上传完成失败
 *    - 如果分片不完整，返回错误
 *    - 如果文件大小不匹配，返回错误
 *    - 清理临时文件
 *
 * 4. 用户可以重新上传
 *    - 新的上传会生成新的 uploadId
 *    - 不会与之前的上传冲突
 */
