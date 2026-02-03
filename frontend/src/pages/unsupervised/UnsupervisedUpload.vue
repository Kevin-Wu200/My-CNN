<template>
  <div class="unsupervised-upload-page">
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
        <h2>无监督病害木检测</h2>
        <p class="description">基于光谱、纹理和空间特征的传统非监督分类方法，无需深度学习模型和人工标注</p>
      </div>

      <div class="method-info">
        <h3 class="info-title">方法说明</h3>
        <ul class="info-list">
          <li>不使用任何深度学习模型</li>
          <li>不依赖人工标注数据</li>
          <li>基于遥感影像的光谱、纹理和空间特征</li>
          <li>适用于无标注或样本不足场景</li>
          <li>结果为候选区域，需要人工验证</li>
        </ul>
      </div>

      <div class="upload-area" @dragover.prevent @drop.prevent="handleDrop">
        <input
          ref="fileInput"
          type="file"
          accept=".jpg,.jpeg,.png,.tif,.tiff"
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
          <p class="upload-hint">支持 jpg、jpeg、png、tif、tiff 格式</p>
        </div>
      </div>

      <div v-if="selectedFile" class="file-info">
        <h3 class="list-title">已选择文件</h3>
        <div class="file-item">
          <div class="file-details">
            <p class="file-name">{{ selectedFile.name }}</p>
            <p class="file-size">{{ formatFileSize(selectedFile.size) }}</p>
          </div>
          <Button variant="secondary" size="small" @click="removeFile">
            移除
          </Button>
        </div>
      </div>

      <div class="parameters-section">
        <h3 class="section-title">检测参数</h3>
        <div class="parameter-group">
          <label class="parameter-label">
            <span>聚类类别数 (K)</span>
            <span class="parameter-hint">推荐 3-6</span>
          </label>
          <input
            v-model.number="nClusters"
            type="range"
            min="2"
            max="10"
            class="parameter-slider"
          />
          <span class="parameter-value">{{ nClusters }}</span>
        </div>

        <div class="parameter-group">
          <label class="parameter-label">
            <span>最小斑块面积阈值</span>
            <span class="parameter-hint">像元数</span>
          </label>
          <input
            v-model.number="minArea"
            type="range"
            min="10"
            max="500"
            step="10"
            class="parameter-slider"
          />
          <span class="parameter-value">{{ minArea }}</span>
        </div>
      </div>

      <div class="action-buttons">
        <Button
          variant="primary"
          :disabled="!selectedFile || isDetecting"
          @click="handleDetect"
        >
          {{ isDetecting ? '检测中...' : '开始检测' }}
        </Button>
        <Button
          variant="secondary"
          :disabled="isDetecting"
          @click="handleReset"
        >
          重置
        </Button>
      </div>

      <div v-if="detectionStatus" class="detection-status" :class="detectionStatus.type">
        <p class="status-message">{{ detectionStatus.message }}</p>
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
const selectedFile = ref<File | null>(null)
const nClusters = ref(4)
const minArea = ref(50)
const isDetecting = ref(false)
const detectionStatus = ref<{ type: 'success' | 'error'; message: string } | null>(null)

// 订阅任务状态
const currentTask = ref<EnhancedTask | null>(null)
let unsubscribe: (() => void) | null = null

// 计算弹窗显示状态
const popupVisible = computed(() => {
  return currentTask.value !== null && currentTask.value.status === 'running'
})

const popupTaskType = computed(() => {
  return currentTask.value?.type === 'unsupervised' ? 'unsupervised' : 'detection'
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
  if (files && files.length > 0) {
    selectedFile.value = files[0]
    detectionStatus.value = null
  }
}

const handleDrop = (event: DragEvent) => {
  const files = event.dataTransfer?.files
  if (files && files.length > 0) {
    selectedFile.value = files[0]
    detectionStatus.value = null
  }
}

const removeFile = () => {
  selectedFile.value = null
  if (fileInput.value) {
    fileInput.value.value = ''
  }
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

const handleDetect = async () => {
  if (!selectedFile.value) return

  isDetecting.value = true

  try {
    // 第一步：启动任务
    await taskManager.startUnsupervisedTask(selectedFile.value, {
      nClusters: nClusters.value,
      minArea: minArea.value,
    })

    detectionStatus.value = {
      type: 'success',
      message: '检测已启动',
    }

    // 第二步：跳转到任务进度页面
    // 禁止在进度页面内部启动任务，任务启动逻辑只在此处执行
    router.push('/task-progress')
  } catch (error: any) {
    detectionStatus.value = {
      type: 'error',
      message: error.message || '检测失败',
    }
  } finally {
    isDetecting.value = false
  }
}

const handleReset = () => {
  selectedFile.value = null
  nClusters.value = 4
  minArea.value = 50
  detectionStatus.value = null
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
.unsupervised-upload-page {
  display: flex;
  justify-content: center;
  padding: 24px;
}

.upload-card {
  width: 100%;
  max-width: 700px;
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
  color: #666;
  margin: 0;
}

.method-info {
  background-color: #f0f9ff;
  border-left: 4px solid #0066cc;
  padding: 16px;
  border-radius: 8px;
  margin-bottom: 24px;
}

.info-title {
  font-size: 14px;
  font-weight: 600;
  color: #0066cc;
  margin: 0 0 12px 0;
}

.info-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.info-list li {
  font-size: 13px;
  color: #333;
  padding: 4px 0;
  padding-left: 20px;
  position: relative;
}

.info-list li:before {
  content: '✓';
  position: absolute;
  left: 0;
  color: #0066cc;
  font-weight: bold;
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

.file-info {
  margin-bottom: 20px;
}

.list-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin: 0 0 12px 0;
}

.file-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px;
  background-color: #f9f9f9;
  border-radius: 8px;
}

.file-details {
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

.parameters-section {
  background-color: #f9f9f9;
  padding: 16px;
  border-radius: 8px;
  margin-bottom: 20px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin: 0 0 16px 0;
}

.parameter-group {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.parameter-group:last-child {
  margin-bottom: 0;
}

.parameter-label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 120px;
  font-size: 13px;
  font-weight: 500;
  color: #333;
}

.parameter-hint {
  font-size: 11px;
  color: #999;
  font-weight: normal;
}

.parameter-slider {
  flex: 1;
  height: 6px;
  border-radius: 3px;
  background: #e0e0e0;
  outline: none;
  -webkit-appearance: none;
}

.parameter-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #0066cc;
  cursor: pointer;
}

.parameter-slider::-moz-range-thumb {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #0066cc;
  cursor: pointer;
  border: none;
}

.parameter-value {
  font-size: 14px;
  font-weight: 600;
  color: #0066cc;
  min-width: 40px;
  text-align: right;
}

.action-buttons {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}

.action-buttons button {
  flex: 1;
}

.detection-status {
  border-radius: 8px;
  padding: 12px;
}

.detection-status.success {
  background-color: #f0f9ff;
  border-left: 4px solid #0066cc;
}

.detection-status.error {
  background-color: #fff5f5;
  border-left: 4px solid #ff3b30;
}

.status-message {
  font-size: 14px;
  margin: 0;
}

.detection-status.success .status-message {
  color: #0066cc;
}

.detection-status.error .status-message {
  color: #ff3b30;
}
</style>
