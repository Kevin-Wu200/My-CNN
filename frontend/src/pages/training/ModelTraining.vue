<template>
  <div class="training-page">
    <Card class="training-card">
      <div class="card-header">
        <h2>模型训练</h2>
      </div>

      <div class="control-section">
        <div class="button-group">
          <Button
            variant="primary"
            :disabled="isTraining"
            @click="startTraining"
          >
            启动训练
          </Button>
          <Button
            variant="danger"
            :disabled="!isTraining"
            @click="stopTraining"
          >
            停止训练
          </Button>
        </div>
      </div>

      <div class="progress-section">
        <div class="progress-info">
          <span class="progress-label">训练进度</span>
          <span class="progress-value">{{ trainingProgress }}%</span>
        </div>
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: trainingProgress + '%' }" />
        </div>
      </div>

      <div class="status-section">
        <h3 class="section-title">训练状态</h3>
        <div class="status-info">
          <p><span class="label">状态：</span><span class="value">{{ trainingStatus }}</span></p>
          <p><span class="label">已用时间：</span><span class="value">{{ elapsedTime }}</span></p>
          <p><span class="label">当前轮数：</span><span class="value">{{ currentEpoch }}/{{ totalEpochs }}</span></p>
          <p><span class="label">损失值：</span><span class="value">{{ currentLoss }}</span></p>
        </div>
      </div>

      <div class="log-section">
        <ToggleButton :isOpen="showLogs" @toggle="showLogs = !showLogs">
          训练日志
        </ToggleButton>

        <div v-if="showLogs" class="log-content">
          <div class="log-list">
            <p v-for="(log, index) in trainingLogs" :key="index" class="log-item">
              {{ log }}
            </p>
          </div>
        </div>
      </div>

      <div class="action-buttons">
        <Button variant="secondary" @click="goToPreviousStep">
          上一步
        </Button>
        <Button
          variant="primary"
          :disabled="trainingProgress < 100"
          @click="goToNextStep"
        >
          完成
        </Button>
      </div>
    </Card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import Card from '@/components/common/Card.vue'
import Button from '@/components/common/Button.vue'
import ToggleButton from '@/components/common/ToggleButton.vue'

const router = useRouter()
const isTraining = ref(false)
const showLogs = ref(false)
const trainingProgress = ref(0)
const trainingStatus = ref('未开始')
const elapsedTime = ref('0:00')
const currentEpoch = ref(0)
const totalEpochs = ref(100)
const currentLoss = ref('0.0000')
const trainingLogs = ref<string[]>([])
let trainingInterval: number | null = null
let startTime: number = 0

const startTraining = () => {
  isTraining.value = true
  trainingStatus.value = '训练中'
  trainingProgress.value = 0
  currentEpoch.value = 0
  trainingLogs.value = ['[INFO] 训练任务已启动', '[INFO] 加载模型配置...']
  startTime = Date.now()

  trainingInterval = window.setInterval(() => {
    if (trainingProgress.value < 100) {
      trainingProgress.value += Math.random() * 5
      if (trainingProgress.value > 100) trainingProgress.value = 100

      currentEpoch.value = Math.floor((trainingProgress.value / 100) * totalEpochs.value)
      currentLoss.value = (Math.random() * 0.5 + 0.1).toFixed(4)

      const elapsed = Math.floor((Date.now() - startTime) / 1000)
      const minutes = Math.floor(elapsed / 60)
      const seconds = elapsed % 60
      elapsedTime.value = `${minutes}:${seconds.toString().padStart(2, '0')}`

      if (Math.random() > 0.7) {
        trainingLogs.value.push(
          `[INFO] Epoch ${currentEpoch.value}/${totalEpochs.value} - Loss: ${currentLoss.value}`
        )
      }
    } else {
      trainingStatus.value = '已完成'
      isTraining.value = false
      if (trainingInterval) clearInterval(trainingInterval)
    }
  }, 1000)
}

const stopTraining = () => {
  isTraining.value = false
  trainingStatus.value = '已停止'
  if (trainingInterval) clearInterval(trainingInterval)
  trainingLogs.value.push('[INFO] 训练任务已停止')
}

const goToPreviousStep = () => {
  router.push('/training/model-config')
}

const goToNextStep = () => {
  router.push('/detection/upload')
}

onUnmounted(() => {
  if (trainingInterval) clearInterval(trainingInterval)
})
</script>

<style scoped>
.training-page {
  display: flex;
  justify-content: center;
  padding: 24px;
}

.training-card {
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
  margin: 0;
}

.control-section {
  margin-bottom: 24px;
}

.button-group {
  display: flex;
  gap: 12px;
}

.button-group button {
  flex: 1;
}

.progress-section {
  margin-bottom: 24px;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 14px;
}

.progress-label {
  font-weight: 500;
  color: #333;
}

.progress-value {
  color: #0066cc;
  font-weight: 600;
}

.progress-bar {
  width: 100%;
  height: 8px;
  background-color: #f0f0f0;
  border-radius: 4px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background-color: #0066cc;
  transition: width 0.3s;
}

.status-section {
  margin-bottom: 24px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin: 0 0 12px 0;
}

.status-info {
  background-color: #f9f9f9;
  border-radius: 8px;
  padding: 12px;
}

.status-info p {
  margin: 8px 0;
  font-size: 13px;
  display: flex;
  justify-content: space-between;
}

.label {
  color: #666;
  font-weight: 500;
}

.value {
  color: #333;
  font-family: 'Monaco', 'Courier New', monospace;
}

.log-section {
  margin-bottom: 24px;
}

.log-content {
  margin-top: 12px;
  background-color: #f9f9f9;
  border-radius: 8px;
  padding: 12px;
  max-height: 300px;
  overflow-y: auto;
}

.log-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.log-item {
  font-size: 12px;
  color: #666;
  font-family: 'Monaco', 'Courier New', monospace;
  margin: 0;
  word-break: break-all;
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
