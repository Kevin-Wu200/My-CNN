<template>
  <div class="sample-upload-page">
    <Card class="upload-card">
      <div class="card-header">
        <div class="header-top">
          <h2>训练样本上传</h2>
          <div
            class="info-icon"
            @mouseenter="startTooltipTimer"
            @mouseleave="hideTooltip"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="16" x2="12" y2="12" />
              <line x1="12" y1="8" x2="12.01" y2="8" />
            </svg>
            <div v-if="showTooltip" class="tooltip-popover">
              <div v-for="(section, index) in tooltipContent.sections" :key="index" class="tooltip-section">
                <h4 class="tooltip-heading">{{ section.heading }}</h4>
                <div class="tooltip-content">
                  <p v-for="(line, lineIndex) in section.content" :key="lineIndex" class="tooltip-line">
                    {{ line }}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
        <p class="description">请上传包含 GeoJSON 标注文件的训练样本（ZIP 或 RAR 格式，压缩包内支持 jpg / png / tif 影像）</p>
      </div>

      <div class="upload-area" @dragover.prevent @drop.prevent="handleDrop">
        <input
          ref="fileInput"
          type="file"
          accept=".zip,.rar"
          @change="handleFileSelect"
          style="display: none"
        />
        <div class="upload-content" @click="triggerFileInput">
          <svg class="upload-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="17 8 12 3 7 8" />
            <line x1="12" y1="3" x2="12" y2="15" />
          </svg>
          <p class="upload-text">拖拽文件到此处或点击选择</p>
          <p class="upload-hint">支持 ZIP 或 RAR 格式</p>
        </div>
      </div>

      <div v-if="selectedFile" class="file-info">
        <p class="file-name">{{ selectedFile.name }}</p>
        <p class="file-size">{{ formatFileSize(selectedFile.size) }}</p>
      </div>

      <div v-if="validationStatus" class="validation-result" :class="validationStatus.type">
        <p class="status-message">{{ validationStatus.message }}</p>
        <ul v-if="validationStatus.details" class="status-details">
          <li v-for="(detail, index) in validationStatus.details" :key="index">
            {{ detail }}
          </li>
        </ul>
      </div>

      <div class="action-buttons">
        <Button
          variant="primary"
          :disabled="!selectedFile || isUploading"
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

      <div v-if="validationStatus?.type === 'success'" class="next-step">
        <Button variant="primary" @click="goToNextStep">
          进入下一步
        </Button>
      </div>
    </Card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import Card from '@/components/common/Card.vue'
import Button from '@/components/common/Button.vue'
import { apiClient } from '@/services/api'
import { UPLOAD_TOOLTIPS } from '@/constants'

const router = useRouter()
const fileInput = ref<HTMLInputElement>()
const selectedFile = ref<File | null>(null)
const isUploading = ref(false)
const showTooltip = ref(false)
const tooltipTimer = ref<ReturnType<typeof setTimeout> | null>(null)
const validationStatus = ref<{
  type: 'success' | 'error'
  message: string
  details?: string[]
} | null>(null)

const tooltipContent = UPLOAD_TOOLTIPS.TRAINING_SAMPLE

const triggerFileInput = () => {
  fileInput.value?.click()
}

const handleFileSelect = (event: Event) => {
  const target = event.target as HTMLInputElement
  const files = target.files
  if (files && files.length > 0) {
    selectedFile.value = files[0]
    validationStatus.value = null
  }
}

const handleDrop = (event: DragEvent) => {
  const files = event.dataTransfer?.files
  if (files && files.length > 0) {
    selectedFile.value = files[0]
    validationStatus.value = null
  }
}

const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i]
}

const startTooltipTimer = () => {
  if (tooltipTimer.value) {
    clearTimeout(tooltipTimer.value)
  }
  tooltipTimer.value = setTimeout(() => {
    showTooltip.value = true
  }, 500)
}

const hideTooltip = () => {
  if (tooltipTimer.value) {
    clearTimeout(tooltipTimer.value)
    tooltipTimer.value = null
  }
  tooltipTimer.value = setTimeout(() => {
    showTooltip.value = false
  }, 1000)
}

const handleUpload = async () => {
  if (!selectedFile.value) return

  isUploading.value = true
  try {
    const response = await apiClient.upload('/training/upload', selectedFile.value)

    // 自动校验坐标系
    const coordinateCheckResult = await apiClient.post('/training/check-coordinates', {
      taskId: response.taskId
    })

    if (coordinateCheckResult.coordinatesMatch) {
      validationStatus.value = {
        type: 'success',
        message: '坐标系核对完成',
        details: ['GeoJSON 文件已识别', '样本数据完整', '坐标系统一致'],
      }
    } else {
      validationStatus.value = {
        type: 'success',
        message: '坐标系不同，已对GeoJSON文件进行投影处理',
        details: ['GeoJSON 文件已识别', '样本数据完整', '已自动投影到影像坐标系'],
      }
    }
  } catch (error: any) {
    validationStatus.value = {
      type: 'error',
      message: error.message || '上传失败，请检查文件格式',
      details: error.details || [],
    }
  } finally {
    isUploading.value = false
  }
}

const handleReset = () => {
  selectedFile.value = null
  validationStatus.value = null
  if (fileInput.value) {
    fileInput.value.value = ''
  }
}

const goToNextStep = () => {
  router.push('/training/preprocess')
}
</script>

<style scoped>
.sample-upload-page {
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

.header-top {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 8px;
}

.card-header h2 {
  font-size: 20px;
  font-weight: 600;
  color: #333;
  margin: 0;
  flex: 1;
}

.info-icon {
  position: relative;
  width: 20px;
  height: 20px;
  flex-shrink: 0;
  cursor: help;
}

.info-icon svg {
  width: 100%;
  height: 100%;
  color: #ccc;
  stroke-width: 2;
  transition: color 0.2s;
}

.info-icon:hover svg {
  color: #999;
}

.tooltip-popover {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 8px;
  background-color: #fff;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  padding: 16px;
  width: 320px;
  z-index: 1000;
  animation: tooltipFadeIn 0.2s ease-out;
}

@keyframes tooltipFadeIn {
  from {
    opacity: 0;
    transform: translateY(-4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.tooltip-section {
  margin-bottom: 12px;
}

.tooltip-section:last-child {
  margin-bottom: 0;
}

.tooltip-heading {
  font-size: 13px;
  font-weight: 600;
  color: #333;
  margin: 0 0 8px 0;
}

.tooltip-content {
  font-size: 12px;
  color: #666;
  line-height: 1.6;
}

.tooltip-line {
  margin: 4px 0;
  white-space: pre-wrap;
  word-break: break-word;
}

.tooltip-line:first-child {
  margin-top: 0;
}

.tooltip-line:last-child {
  margin-bottom: 0;
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

.file-info {
  background-color: #f5f5f5;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 20px;
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

.validation-result {
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 20px;
}

.validation-result.success {
  background-color: #f0f9ff;
  border-left: 4px solid #0066cc;
}

.validation-result.error {
  background-color: #fff5f5;
  border-left: 4px solid #ff3b30;
}

.status-message {
  font-size: 14px;
  font-weight: 500;
  margin: 0 0 8px 0;
}

.validation-result.success .status-message {
  color: #0066cc;
}

.validation-result.error .status-message {
  color: #ff3b30;
}

.status-details {
  list-style: none;
  padding: 0;
  margin: 0;
  font-size: 13px;
}

.status-details li {
  padding: 4px 0;
  color: #666;
}

.action-buttons {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}

.action-buttons button {
  flex: 1;
}

.next-step {
  display: flex;
  justify-content: center;
}

.next-step button {
  width: 100%;
}
</style>
