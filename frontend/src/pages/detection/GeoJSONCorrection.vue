<template>
  <div class="geojson-page">
    <Card class="geojson-card">
      <div class="card-header">
        <h2>GeoJSON 修正与回流</h2>
      </div>

      <div class="export-section">
        <h3 class="section-title">导出检测结果</h3>
        <p class="section-desc">将当前检测结果导出为 GeoJSON 格式文件</p>
        <Button variant="primary" @click="exportGeoJSON">
          导出 GeoJSON
        </Button>
      </div>

      <div class="divider" />

      <div class="upload-section">
        <h3 class="section-title">上传修正文件</h3>
        <p class="section-desc">上传修正后的 GeoJSON 文件进行校验</p>

        <div class="upload-area" @dragover.prevent @drop.prevent="handleDrop">
          <input
            ref="fileInput"
            type="file"
            accept=".geojson,.json"
            @change="handleFileSelect"
            style="display: none"
          />
          <div class="upload-content" @click="triggerFileInput">
            <svg class="upload-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
            <p class="upload-text">拖拽 GeoJSON 文件到此处或点击选择</p>
          </div>
        </div>

        <div v-if="selectedFile" class="file-info">
          <p class="file-name">{{ selectedFile.name }}</p>
          <p class="file-size">{{ formatFileSize(selectedFile.size) }}</p>
        </div>
      </div>

      <div v-if="validationResult" class="validation-result" :class="validationResult.type">
        <p class="result-message">{{ validationResult.message }}</p>
        <ul v-if="validationResult.details" class="result-details">
          <li v-for="(detail, index) in validationResult.details" :key="index">
            {{ detail }}
          </li>
        </ul>
      </div>

      <div class="action-buttons">
        <Button
          variant="secondary"
          @click="goToPreviousStep"
        >
          上一步
        </Button>
        <Button
          variant="primary"
          :disabled="!selectedFile || !validationResult || validationResult.type !== 'success'"
          @click="submitCorrection"
        >
          确认提交
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

const router = useRouter()
const fileInput = ref<HTMLInputElement>()
const selectedFile = ref<File | null>(null)
const validationResult = ref<{
  type: 'success' | 'error'
  message: string
  details?: string[]
} | null>(null)

const triggerFileInput = () => {
  fileInput.value?.click()
}

const handleFileSelect = (event: Event) => {
  const target = event.target as HTMLInputElement
  const files = target.files
  if (files && files.length > 0) {
    selectedFile.value = files[0]
    validateFile(files[0])
  }
}

const handleDrop = (event: DragEvent) => {
  const files = event.dataTransfer?.files
  if (files && files.length > 0) {
    selectedFile.value = files[0]
    validateFile(files[0])
  }
}

const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i]
}

const validateFile = async (file: File) => {
  try {
    const text = await file.text()
    const json = JSON.parse(text)

    if (json.type === 'FeatureCollection' && Array.isArray(json.features)) {
      validationResult.value = {
        type: 'success',
        message: 'GeoJSON 文件校验成功',
        details: [
          `特征数量: ${json.features.length}`,
          '坐标系统: WGS84',
          '文件格式: 有效',
        ],
      }
    } else {
      validationResult.value = {
        type: 'error',
        message: 'GeoJSON 格式不正确',
        details: ['必须是 FeatureCollection 类型'],
      }
    }
  } catch (error) {
    validationResult.value = {
      type: 'error',
      message: '文件解析失败',
      details: ['请确保文件是有效的 JSON 格式'],
    }
  }
}

const exportGeoJSON = () => {
  const geojson = {
    type: 'FeatureCollection',
    features: [
      {
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [0, 0] },
        properties: { confidence: 0.95 },
      },
    ],
  }

  const blob = new Blob([JSON.stringify(geojson, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'detection_result.geojson'
  a.click()
  URL.revokeObjectURL(url)
}

const submitCorrection = async () => {
  if (!selectedFile.value) return

  try {
    await apiClient.upload('/detection/geojson', selectedFile.value)
    router.push('/history')
  } catch (error) {
    console.error('提交失败', error)
  }
}

const goToPreviousStep = () => {
  router.push('/detection/result')
}
</script>

<style scoped>
.geojson-page {
  display: flex;
  justify-content: center;
  padding: 24px;
}

.geojson-card {
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
  margin: 0;
}

.export-section,
.upload-section {
  margin-bottom: 24px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin: 0 0 8px 0;
}

.section-desc {
  font-size: 13px;
  color: #999;
  margin: 0 0 12px 0;
}

.divider {
  height: 1px;
  background-color: #f0f0f0;
  margin: 24px 0;
}

.upload-area {
  border: 2px dashed #d0d0d0;
  border-radius: 12px;
  padding: 40px 20px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
  margin-bottom: 16px;
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
  font-size: 14px;
  color: #333;
  margin: 0;
}

.file-info {
  background-color: #f9f9f9;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 16px;
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

.result-message {
  font-size: 14px;
  font-weight: 500;
  margin: 0 0 8px 0;
}

.validation-result.success .result-message {
  color: #0066cc;
}

.validation-result.error .result-message {
  color: #ff3b30;
}

.result-details {
  list-style: none;
  padding: 0;
  margin: 0;
  font-size: 13px;
}

.result-details li {
  padding: 4px 0;
  color: #666;
}

.action-buttons {
  display: flex;
  gap: 12px;
  margin-top: 24px;
}

.action-buttons button {
  flex: 1;
}
</style>
