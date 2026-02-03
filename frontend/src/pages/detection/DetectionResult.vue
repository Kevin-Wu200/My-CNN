<template>
  <div class="detection-result-page">
    <div class="result-container">
      <div class="image-area">
        <Card class="image-card">
          <div class="image-container">
            <div v-if="imageLoading" class="image-loading">
              <div class="spinner"></div>
              <p>加载中...</p>
            </div>
            <div v-else-if="imageError" class="image-error">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <circle cx="12" cy="12" r="10" />
                <path d="M12 8v4M12 16h.01" />
              </svg>
              <p>{{ imageError }}</p>
            </div>
            <div v-else-if="resultImageUrl" class="image-wrapper">
              <img :src="resultImageUrl" alt="检测结果" @load="onImageLoad" @error="onImageError" />
              <svg
                v-if="imageLoaded"
                class="overlay"
                :viewBox="`0 0 ${imageWidth} ${imageHeight}`"
                preserveAspectRatio="none"
              >
                <g v-for="point in detectionPoints" :key="point.id">
                  <!-- Blue cross -->
                  <line
                    :x1="point.x - 15"
                    :y1="point.y"
                    :x2="point.x + 15"
                    :y2="point.y"
                    class="cross-line"
                  />
                  <line
                    :x1="point.x"
                    :y1="point.y - 15"
                    :x2="point.x"
                    :y2="point.y + 15"
                    class="cross-line"
                  />
                  <!-- Red center point -->
                  <circle :cx="point.x" :cy="point.y" r="4" class="center-point" />
                </g>
              </svg>
            </div>
            <div v-else class="image-placeholder">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <rect x="3" y="3" width="18" height="18" rx="2" />
                <circle cx="8.5" cy="8.5" r="1.5" />
                <path d="M21 15l-5-5L5 21" />
              </svg>
              <p>暂无检测结果</p>
              <p class="placeholder-hint">检测完成后将在此显示结果影像</p>
            </div>
          </div>
        </Card>
      </div>

      <div class="sidebar">
        <Card class="points-card">
          <div class="card-header">
            <h3>检测点位列表</h3>
            <span class="point-count">{{ detectionPoints.length }}</span>
          </div>

          <div class="points-list">
            <div
              v-for="(point, index) in detectionPoints"
              :key="point.id"
              class="point-item"
              :class="{ active: selectedPointId === point.id }"
              @click="selectPoint(point.id)"
              @mouseenter="startHoverTimer(point.id)"
              @mouseleave="clearHoverTimer(point.id)"
            >
              <div class="point-info">
                <p class="point-label">点位 {{ index + 1 }}</p>
                <p class="point-confidence">
                  置信度: {{ (point.confidence * 100).toFixed(1) }}%
                </p>
              </div>
              <div v-if="hoveredPointId === point.id" class="point-tooltip">
                坐标: ({{ Math.round(point.x) }}, {{ Math.round(point.y) }})
              </div>
              <Button variant="danger" size="small" @click.stop="deletePoint(point.id)">
                删除
              </Button>
            </div>
          </div>

          <div class="action-buttons">
            <Button variant="secondary" size="small" @click="addPoint">
              新增点位
            </Button>
            <Button variant="primary" @click="submitResults">
              提交结果
            </Button>
          </div>
        </Card>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import Card from '@/components/common/Card.vue'
import Button from '@/components/common/Button.vue'
import type { DetectionPoint } from '@/types'
import { taskManager } from '@/services/taskManager'

const router = useRouter()
const selectedPointId = ref<string | null>(null)
const detectionPoints = ref<DetectionPoint[]>([
  { id: '1', x: 100, y: 150, confidence: 0.95 },
  { id: '2', x: 200, y: 250, confidence: 0.87 },
  { id: '3', x: 300, y: 180, confidence: 0.92 },
])

// Image display states
const resultImageUrl = ref<string | null>(null)
const imageLoading = ref(false)
const imageError = ref<string | null>(null)
const imageLoaded = ref(false)
const imageWidth = ref(0)
const imageHeight = ref(0)

// Hover tooltip states
const hoveredPointId = ref<string | null>(null)
const hoverTimers = ref<Map<string, NodeJS.Timeout>>(new Map())

const selectPoint = (id: string) => {
  selectedPointId.value = id
}

const deletePoint = (id: string) => {
  detectionPoints.value = detectionPoints.value.filter((p) => p.id !== id)
  if (selectedPointId.value === id) {
    selectedPointId.value = null
  }
}

const addPoint = () => {
  const newId = String(Math.max(...detectionPoints.value.map((p) => parseInt(p.id))) + 1)
  detectionPoints.value.push({
    id: newId,
    x: Math.random() * 400,
    y: Math.random() * 400,
    confidence: Math.random() * 0.3 + 0.7,
  })
}

const submitResults = () => {
  router.push('/detection/geojson')
}

const onImageLoad = (event: Event) => {
  const img = event.target as HTMLImageElement
  imageWidth.value = img.naturalWidth
  imageHeight.value = img.naturalHeight
  imageLoaded.value = true
  imageLoading.value = false
}

const onImageError = () => {
  imageError.value = '影像加载失败，请检查文件格式或重新上传'
  imageLoading.value = false
  imageLoaded.value = false
}

const startHoverTimer = (pointId: string) => {
  const timer = setTimeout(() => {
    hoveredPointId.value = pointId
  }, 1000)
  hoverTimers.value.set(pointId, timer)
}

const clearHoverTimer = (pointId: string) => {
  const timer = hoverTimers.value.get(pointId)
  if (timer) {
    clearTimeout(timer)
    hoverTimers.value.delete(pointId)
  }
  hoveredPointId.value = null
}

onMounted(() => {
  // Try task manager first
  const task = taskManager.getCurrentTask()
  if (task?.type === 'detection' && task.status === 'completed' && task.result) {
    // Load detection points from task result if available
    // For now, use mock data as the detection API is not fully implemented
    detectionPoints.value = [
      { id: '1', x: 100, y: 150, confidence: 0.95 },
      { id: '2', x: 200, y: 250, confidence: 0.87 },
      { id: '3', x: 300, y: 180, confidence: 0.92 },
    ]
  }

  // Simulate loading detection result image
  // In production, this would fetch from API based on detection task ID
  imageLoading.value = true
  setTimeout(() => {
    // Example: set a sample image URL or local path
    resultImageUrl.value = '/api/detection/result-image'
  }, 500)
})

onUnmounted(() => {
  // Clean up all hover timers
  hoverTimers.value.forEach((timer) => clearTimeout(timer))
  hoverTimers.value.clear()
})
</script>

<style scoped>
.detection-result-page {
  display: flex;
  justify-content: center;
  padding: 24px;
}

.result-container {
  display: grid;
  grid-template-columns: 1fr 300px;
  gap: 24px;
  width: 100%;
  max-width: 1200px;
}

.image-area {
  display: flex;
}

.image-card {
  width: 100%;
  aspect-ratio: 1;
}

.image-container {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  position: relative;
  background-color: #fafafa;
}

.image-wrapper {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.image-wrapper img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

.overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.cross-line {
  stroke: #0066cc;
  stroke-width: 1.5;
  stroke-linecap: round;
}

.center-point {
  fill: #ff3b30;
  stroke: none;
}

.image-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: #999;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 2px solid #f0f0f0;
  border-top-color: #0066cc;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.image-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: #ff3b30;
  text-align: center;
  padding: 24px;
}

.image-error svg {
  width: 48px;
  height: 48px;
}

.image-error p {
  font-size: 13px;
  margin: 0;
  line-height: 1.4;
}

.image-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 12px;
  color: #999;
}

.image-placeholder svg {
  width: 64px;
  height: 64px;
}

.image-placeholder p {
  font-size: 14px;
  margin: 0;
}

.placeholder-hint {
  font-size: 12px;
  color: #ccc;
}

.sidebar {
  display: flex;
  flex-direction: column;
}

.points-card {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #f0f0f0;
}

.card-header h3 {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin: 0;
}

.point-count {
  font-size: 12px;
  background-color: #f0f0f0;
  color: #666;
  padding: 4px 8px;
  border-radius: 4px;
}

.points-list {
  flex: 1;
  overflow-y: auto;
  margin-bottom: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.point-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px;
  background-color: #f9f9f9;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
}

.point-item:hover {
  background-color: #f0f0f0;
}

.point-item.active {
  background-color: #e8f4ff;
  border-left: 3px solid #0066cc;
}

.point-info {
  flex: 1;
}

.point-label {
  font-size: 13px;
  font-weight: 500;
  color: #333;
  margin: 0 0 4px 0;
}

.point-confidence {
  font-size: 12px;
  color: #999;
  margin: 0;
}

.point-tooltip {
  position: absolute;
  bottom: 100%;
  left: 50%;
  transform: translateX(-50%);
  background-color: #333;
  color: #fff;
  font-size: 12px;
  padding: 6px 10px;
  border-radius: 4px;
  white-space: nowrap;
  margin-bottom: 8px;
  animation: fadeIn 0.2s ease-in;
  pointer-events: none;
  z-index: 10;
}

.point-tooltip::after {
  content: '';
  position: absolute;
  top: 100%;
  left: 50%;
  transform: translateX(-50%);
  border: 4px solid transparent;
  border-top-color: #333;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateX(-50%) translateY(4px);
  }
  to {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
  }
}

.action-buttons {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.action-buttons button {
  width: 100%;
}

@media (max-width: 1024px) {
  .result-container {
    grid-template-columns: 1fr;
  }

  .image-card {
    aspect-ratio: auto;
    min-height: 400px;
  }
}
</style>
