<template>
  <div class="preprocess-page">
    <Card class="status-card">
      <div class="card-header">
        <h2>样本构建与预处理</h2>
      </div>

      <div class="status-section">
        <h3 class="section-title">多时相影像读取状态</h3>
        <div class="status-list">
          <div v-for="image in imageStatus" :key="image.id" class="status-item">
            <div class="status-indicator" :class="image.status" />
            <div class="status-info">
              <p class="status-name">{{ image.name }}</p>
              <p class="status-detail">{{ image.detail }}</p>
            </div>
          </div>
        </div>
      </div>

      <div class="config-section">
        <h3 class="section-title">样本构建方式选择</h3>
        <div class="config-options">
          <label class="radio-option">
            <input
              v-model="buildMethod"
              type="radio"
              value="pixel"
              name="buildMethod"
            />
            <span class="radio-label">
              <span class="label-text">像素级构建</span>
              <span class="label-desc">逐像素进行样本构建</span>
            </span>
          </label>
          <label class="radio-option">
            <input
              v-model="buildMethod"
              type="radio"
              value="superpixel"
              name="buildMethod"
            />
            <span class="radio-label">
              <span class="label-text">超像素级构建</span>
              <span class="label-desc">基于超像素分割进行样本构建</span>
            </span>
          </label>
        </div>
      </div>

      <div class="action-buttons">
        <Button variant="secondary" @click="goToPreviousStep">
          上一步
        </Button>
        <Button variant="primary" @click="goToNextStep">
          下一步
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

const router = useRouter()
const buildMethod = ref('pixel')

const imageStatus = ref([
  { id: 1, name: '2020年影像', status: 'completed', detail: '已读取，分辨率 512×512' },
  { id: 2, name: '2021年影像', status: 'completed', detail: '已读取，分辨率 512×512' },
  { id: 3, name: '2022年影像', status: 'completed', detail: '已读取，分辨率 512×512' },
])

const goToPreviousStep = () => {
  router.push('/training/upload')
}

const goToNextStep = () => {
  router.push('/training/model-config')
}
</script>

<style scoped>
.preprocess-page {
  display: flex;
  justify-content: center;
  padding: 24px;
}

.status-card {
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

.status-section,
.config-section {
  margin-bottom: 24px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin: 0 0 16px 0;
}

.status-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.status-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px;
  background-color: #f9f9f9;
  border-radius: 8px;
}

.status-indicator {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  flex-shrink: 0;
  margin-top: 4px;
}

.status-indicator.completed {
  background-color: #34c759;
}

.status-indicator.processing {
  background-color: #ff9500;
}

.status-indicator.failed {
  background-color: #ff3b30;
}

.status-info {
  flex: 1;
}

.status-name {
  font-size: 14px;
  font-weight: 500;
  color: #333;
  margin: 0 0 4px 0;
}

.status-detail {
  font-size: 12px;
  color: #999;
  margin: 0;
}

.config-options {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.radio-option {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.radio-option:hover {
  background-color: #f9f9f9;
  border-color: #e0e0e0;
}

.radio-option input[type='radio'] {
  cursor: pointer;
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.radio-label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
}

.label-text {
  font-size: 14px;
  font-weight: 500;
  color: #333;
}

.label-desc {
  font-size: 12px;
  color: #999;
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
