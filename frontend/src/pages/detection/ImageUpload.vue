<template>
  <div class="image-upload-page">
    <ProgressPopup
      :is-visible="popupVisible"
      :task-type="popupTaskType"
      :progress="popupProgress"
      :current-stage="popupStage"
      :status="popupStatus"
      @close="closePopup"
    />
    <Card class="upload-card">
      <div class="card-header">
        <h2>待检测影像上传</h2>
        <p class="description">请上传待检测影像（支持 jpg、jpeg、png、tif、tiff 格式），不支持 GeoJSON 文件</p>
      </div>

      <div class="upload-area" @dragover.prevent @drop.prevent="handleDrop">
        <input
          ref="fileInput"
          type="file"
          accept=".jpg,.jpeg,.png,.tif,.tiff"
          multiple
          @change="handleFileSelect"
          style="display: none"
        />
        <div class="upload-content" @click="triggerFileInput">
          <svg class="upload-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <rect x="3" y="3" width="18" height="18" rx="2" />
            <circle cx="8.5" cy="8.5" r="1.5" />
            <path d="M21 15l-5-5L5 21" />
          </svg>
          <p class="upload-text">拖拽影像文件到此处或点击选择</p>
          <p class="upload-hint">支持 jpg、jpeg、png、tif、tiff 格式，可上传多个文件</p>
        </div>
      </div>

      <div v-if="selectedFiles.length > 0" class="files-list">
        <h3 class="list-title">已选择文件</h3>
        <div class="file-items">
          <div v-for="(file, index) in selectedFiles" :key="index" class="file-item">
            <div class="file-info">
              <p class="file-name">{{ file.name }}</p>
              <p class="file-size">{{ formatFileSize(file.size) }}</p>
            </div>
            <Button variant="secondary" size="small" @click="removeFile(index)">
              移除
            </Button>
          </div>
        </div>
      </div>

      <div class="temporal-section">
        <h3 class="section-title">影像时相</h3>
        <div class="temporal-options">
          <label class="radio-option">
            <input
              v-model="temporalType"
              type="radio"
              value="single"
              name="temporal"
            />
            <span class="radio-label">单时相</span>
          </label>
          <label class="radio-option">
            <input
              v-model="temporalType"
              type="radio"
              value="multi"
              name="temporal"
            />
            <span class="radio-label">多时相</span>
          </label>
        </div>
      </div>

      <div class="action-buttons">
        <Button
          variant="primary"
          :disabled="selectedFiles.length === 0 || isUploading"
          @click="handleUpload"
        >
          {{ isUploading ? '上传中...' : '上传' }}
        </Button>
        <Button
          variant="secondary"
          :disabled="isUploading"
          @click="handleReset"
        >
          重置
        </Button>
      </div>

      <div v-if="uploadStatus" class="upload-status" :class="uploadStatus.type">
        <p class="status-message">{{ uploadStatus.message }}</p>
      </div>
    </Card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import Card from '@/components/common/Card.vue'
import Button from '@/components/common/Button.vue'
import ProgressPopup from '@/components/common/ProgressPopup.vue'
import { taskManager } from '@/services/taskManager'
import type { EnhancedTask } from '@/types'

const router = useRouter()
const fileInput = ref<HTMLInputElement>()
const selectedFiles = ref<File[]>([])
const temporalType = ref('single')
const isUploading = ref(false)
const uploadStatus = ref<{ type: 'success' | 'error'; message: string } | null>(null)

// 订阅任务状态
const currentTask = ref<EnhancedTask | null>(null)
let unsubscribe: (() => void) | null = null

// 计算弹窗显示状态
const popupVisible = computed(() => {
  return currentTask.value !== null && currentTask.value.status === 'running'
})

const popupTaskType = computed(() => {
  return currentTask.value?.type === 'detection' ? 'detection' : 'unsupervised'
})

const popupProgress = computed(() => {
  return currentTask.value?.progress || 0
})

const popupStage = computed(() => {
  return currentTask.value?.currentStage || ''
})

const popupStatus = computed(() => {
  if (!currentTask.value) return 'processing'
  if (currentTask.value.status === 'completed') return 'completed'
  if (currentTask.value.status === 'failed') return 'failed'
  return 'processing'
})

const triggerFileInput = () => {
  fileInput.value?.click()
}

const handleFileSelect = (event: Event) => {
  const target = event.target as HTMLInputElement
  const files = target.files
  if (files) {
    selectedFiles.value = Array.from(files)
    uploadStatus.value = null
  }
}

const handleDrop = (event: DragEvent) => {
  const files = event.dataTransfer?.files
  if (files) {
    selectedFiles.value = Array.from(files)
    uploadStatus.value = null
  }
}

const removeFile = (index: number) => {
  selectedFiles.value.splice(index, 1)
}

const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i]
}

const closePopup = () => {
  // 弹窗关闭时，不做任何操作
  // 任务状态由 TaskManager 管理
}

const handleUpload = async () => {
  if (selectedFiles.value.length === 0) return

  isUploading.value = true

  try {
    // 第一步：启动任务
    await taskManager.startDetectionTask(selectedFiles.value, {
      temporalType: temporalType.value,
    })

    uploadStatus.value = {
      type: 'success',
      message: '文件上传成功',
    }

    // 第二步：跳转到任务进度页面
    // 禁止在进度页面内部启动任务，任务启动逻辑只在此处执行
    router.push('/task-progress')
  } catch (error: any) {
    uploadStatus.value = {
      type: 'error',
      message: error.message || '上传失败',
    }
  } finally {
    isUploading.value = false
  }
}

const handleReset = () => {
  selectedFiles.value = []
  uploadStatus.value = null
  if (fileInput.value) {
    fileInput.value.value = ''
  }
}

/**
 * 页面挂载时订阅任务状态
 */
onMounted(() => {
  currentTask.value = taskManager.getCurrentTask()
  unsubscribe = taskManager.subscribeToTask((task) => {
    currentTask.value = task
  })
})

/**
 * 页面卸载时取消订阅
 */
onUnmounted(() => {
  if (unsubscribe) {
    unsubscribe()
  }
})
</script>

<style scoped>
.image-upload-page {
  display: flex;
  justify-content: center;
  padding: 24px;
}

.upload-card {
  width: 100%;
  max-width: 600px;
}

.card-header {
  margin-bottom: 24px;
}

.card-header h2 {
  font-size: 20px;
  font-weight: 600;
  color: #333;
  margin-bottom: 8px;
}

.description {
  font-size: 14px;
  color: #999;
  margin: 0;
}

.upload-area {
  border: 2px dashed #d0d0d0;
  border-radius: 12px;
  padding: 40px 20px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
  margin-bottom: 20px;
}

.upload-area:hover {
  border-color: #0066cc;
  background-color: #f9f9f9;
}

.upload-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.upload-icon {
  width: 48px;
  height: 48px;
  color: #0066cc;
}

.upload-text {
  font-size: 16px;
  font-weight: 500;
  color: #333;
  margin: 0;
}

.upload-hint {
  font-size: 12px;
  color: #999;
  margin: 0;
}

.files-list {
  margin-bottom: 20px;
}

.list-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin: 0 0 12px 0;
}

.file-items {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.file-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px;
  background-color: #f9f9f9;
  border-radius: 8px;
}

.file-info {
  flex: 1;
}

.file-name {
  font-size: 14px;
  font-weight: 500;
  color: #333;
  margin: 0 0 4px 0;
  word-break: break-all;
}

.file-size {
  font-size: 12px;
  color: #999;
  margin: 0;
}

.temporal-section {
  margin-bottom: 20px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin: 0 0 12px 0;
}

.temporal-options {
  display: flex;
  gap: 16px;
}

.radio-option {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.radio-option input[type='radio'] {
  cursor: pointer;
}

.radio-label {
  font-size: 14px;
  color: #333;
}

.action-buttons {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}

.action-buttons button {
  flex: 1;
}

.upload-status {
  border-radius: 8px;
  padding: 12px;
}

.upload-status.success {
  background-color: #f0f9ff;
  border-left: 4px solid #0066cc;
}

.upload-status.error {
  background-color: #fff5f5;
  border-left: 4px solid #ff3b30;
}

.status-message {
  font-size: 14px;
  margin: 0;
}

.upload-status.success .status-message {
  color: #0066cc;
}

.upload-status.error .status-message {
  color: #ff3b30;
}
</style>
