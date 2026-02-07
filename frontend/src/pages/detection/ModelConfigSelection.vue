<template>
  <div class="model-config-selection-page">
    <Card class="config-card">
      <div class="card-header">
        <h2>选择模型参数配置</h2>
        <p class="description">从已完成的训练任务中选择模型参数配置进行检测</p>
      </div>

      <div v-if="loading" class="loading-state">
        <div class="spinner"></div>
        <p>加载模型配置中...</p>
      </div>

      <div v-else-if="configs.length === 0" class="empty-state">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
          <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm3.5-9c.83 0 1.5-.67 1.5-1.5S16.33 8 15.5 8 14 8.67 14 9.5s.67 1.5 1.5 1.5zm-7 0c.83 0 1.5-.67 1.5-1.5S9.33 8 8.5 8 7 8.67 7 9.5 7.67 11 8.5 11zm3.5 6.5c2.33 0 4.31-1.46 5.11-3.5H6.89c.8 2.04 2.78 3.5 5.11 3.5z" />
        </svg>
        <p>暂无已完成的训练任务</p>
        <p class="empty-hint">请先完成模型训练后再进行检测</p>
        <Button variant="primary" @click="handleGoToTraining">
          去训练模型
        </Button>
      </div>

      <div v-else class="config-list">
        <div class="config-items">
          <div
            v-for="config in configs"
            :key="config.id"
            class="config-item"
            :class="{ selected: selectedConfigId === config.id }"
            @click="selectConfig(config.id)"
          >
            <div class="config-header">
              <h3 class="config-name">{{ config.task_name }}</h3>
              <span class="config-id">ID: {{ config.id }}</span>
            </div>

            <div class="config-details">
              <div class="detail-row">
                <span class="detail-label">CNN 主干:</span>
                <span class="detail-value">{{ config.config.cnnBackbone || '-' }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">时序模块:</span>
                <span class="detail-value">{{ config.config.temporalModule || '-' }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">输入类型:</span>
                <span class="detail-value">{{ config.config.inputType || '-' }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">学习率:</span>
                <span class="detail-value">{{ config.config.learningRate || '-' }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">批大小:</span>
                <span class="detail-value">{{ config.config.batchSize || '-' }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">训练轮数:</span>
                <span class="detail-value">{{ config.config.epochs || '-' }}</span>
              </div>
            </div>

            <div class="config-footer">
              <span class="created-time">
                创建于: {{ formatDate(config.created_at) }}
              </span>
              <span class="completed-time">
                完成于: {{ formatDate(config.completed_at) }}
              </span>
            </div>

            <div v-if="selectedConfigId === config.id" class="selected-badge">
              ✓ 已选择
            </div>
          </div>
        </div>
      </div>

      <div v-if="configs.length > 0" class="action-buttons">
        <Button
          variant="primary"
          :disabled="!selectedConfigId"
          @click="handleConfirm"
        >
          确认选择
        </Button>
        <Button variant="secondary" @click="handleCancel">
          取消
        </Button>
      </div>

      <div v-if="errorMessage" class="error-message">
        <p>{{ errorMessage }}</p>
      </div>
    </Card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import Card from '@/components/common/Card.vue'
import Button from '@/components/common/Button.vue'
import { apiClient } from '@/services/api'

interface ModelConfig {
  id: number
  task_name: string
  config: {
    cnnBackbone?: string
    temporalModule?: string
    inputType?: string
    learningRate?: number
    batchSize?: number
    epochs?: number
  }
  model_path?: string
  created_at?: string
  completed_at?: string
}

const router = useRouter()
const configs = ref<ModelConfig[]>([])
const selectedConfigId = ref<number | null>(null)
const loading = ref(true)
const errorMessage = ref('')

onMounted(async () => {
  await loadConfigs()
})

const loadConfigs = async () => {
  try {
    loading.value = true
    errorMessage.value = ''
    const response = await apiClient.get('/api/detection/model-configs')
    configs.value = response.configs || []
  } catch (error: any) {
    errorMessage.value = error.message || '加载模型配置失败'
  } finally {
    loading.value = false
  }
}

const selectConfig = (configId: number) => {
  selectedConfigId.value = configId
}

const formatDate = (dateStr?: string): string => {
  if (!dateStr) return '-'
  try {
    const date = new Date(dateStr)
    return date.toLocaleString('zh-CN')
  } catch {
    return dateStr
  }
}

const handleConfirm = () => {
  if (!selectedConfigId.value) return

  // 保存选择的配置到 sessionStorage
  const selectedConfig = configs.value.find(c => c.id === selectedConfigId.value)
  if (selectedConfig) {
    sessionStorage.setItem('selectedModelConfig', JSON.stringify(selectedConfig))
    router.push('/detection/upload')
  }
}

const handleCancel = () => {
  router.push('/detection/upload')
}

const handleGoToTraining = () => {
  router.push('/training/upload')
}
</script>

<style scoped>
.model-config-selection-page {
  display: flex;
  justify-content: center;
  padding: 24px;
}

.config-card {
  width: 100%;
  max-width: 900px;
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

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 4px solid #f0f0f0;
  border-top: 4px solid #0066cc;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 16px;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.loading-state p {
  font-size: 14px;
  color: #666;
  margin: 0;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
}

.empty-state svg {
  width: 64px;
  height: 64px;
  color: #ccc;
  margin-bottom: 16px;
}

.empty-state p {
  font-size: 14px;
  color: #666;
  margin: 0 0 8px 0;
}

.empty-hint {
  font-size: 12px;
  color: #999;
  margin-bottom: 16px !important;
}

.config-list {
  margin-bottom: 24px;
}

.config-items {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}

.config-item {
  border: 2px solid #e0e0e0;
  border-radius: 12px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
  background-color: #fff;
}

.config-item:hover {
  border-color: #0066cc;
  box-shadow: 0 2px 8px rgba(0, 102, 204, 0.1);
}

.config-item.selected {
  border-color: #0066cc;
  background-color: #f0f9ff;
  box-shadow: 0 2px 8px rgba(0, 102, 204, 0.2);
}

.config-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
}

.config-name {
  font-size: 16px;
  font-weight: 600;
  color: #333;
  margin: 0;
  flex: 1;
}

.config-id {
  font-size: 12px;
  color: #999;
  background-color: #f5f5f5;
  padding: 4px 8px;
  border-radius: 4px;
  margin-left: 8px;
}

.config-details {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
  padding: 12px;
  background-color: #f9f9f9;
  border-radius: 8px;
}

.detail-row {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
}

.detail-label {
  color: #666;
  font-weight: 500;
}

.detail-value {
  color: #333;
  font-weight: 600;
}

.config-footer {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: #999;
  padding-top: 12px;
  border-top: 1px solid #e0e0e0;
}

.created-time,
.completed-time {
  font-size: 11px;
}

.selected-badge {
  position: absolute;
  top: 12px;
  right: 12px;
  background-color: #0066cc;
  color: white;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
}

.action-buttons {
  display: flex;
  gap: 12px;
  justify-content: center;
}

.action-buttons button {
  min-width: 120px;
}

.error-message {
  background-color: #fff5f5;
  border-left: 4px solid #ff3b30;
  padding: 12px;
  border-radius: 8px;
  margin-top: 16px;
}

.error-message p {
  font-size: 14px;
  color: #ff3b30;
  margin: 0;
}
</style>
