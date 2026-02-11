<template>
  <div class="unsupervised-result-page">
    <Card class="result-card">
      <div class="card-header">
        <h2>检测结果</h2>
        <p class="description">非监督病害木检测结果展示</p>
      </div>

      <div v-if="detectionResult" class="result-content">
        <div class="result-summary">
          <h3 class="summary-title">检测摘要</h3>
          <div class="summary-grid">
            <div class="summary-item">
              <span class="summary-label">检测方法</span>
              <span class="summary-value">{{ detectionResult.method }}</span>
            </div>
            <div class="summary-item">
              <span class="summary-label">聚类类别数</span>
              <span class="summary-value">{{ detectionResult.n_clusters }}</span>
            </div>
            <div class="summary-item">
              <span class="summary-label">候选区域数</span>
              <span class="summary-value">{{ detectionResult.n_candidates }}</span>
            </div>
            <div class="summary-item">
              <span class="summary-label">影像尺寸</span>
              <span class="summary-value">{{ detectionResult.image_shape[0] }} × {{ detectionResult.image_shape[1] }}</span>
            </div>
          </div>
        </div>

        <div class="method-description">
          <h3 class="description-title">方法说明</h3>
          <p class="description-text">{{ detectionResult.description }}</p>
          <div class="warning-box">
            <p class="warning-text">{{ detectionResult.note }}</p>
          </div>
        </div>

        <div class="center-points-section">
          <h3 class="section-title">病害木中心点位 ({{ detectionResult.center_points.length }})</h3>
          <div v-if="detectionResult.center_points.length > 0" class="points-list">
            <div v-for="(point, index) in detectionResult.center_points" :key="index" class="point-item">
              <div class="point-info">
                <span class="point-index">{{ index + 1 }}</span>
                <div class="point-details">
                  <p class="point-coord">坐标: ({{ point.x.toFixed(1) }}, {{ point.y.toFixed(1) }})</p>
                  <p class="point-area">面积: {{ point.area }} 像元</p>
                </div>
              </div>
            </div>
          </div>
          <div v-else class="no-points">
            <p>未发现病害木候选区域</p>
          </div>
        </div>

        <div class="action-buttons">
          <Button variant="primary" @click="handleExportGeoJSON">
            导出 GeoJSON
          </Button>
          <Button variant="secondary" @click="handleBackToUpload">
            返回上传
          </Button>
        </div>
      </div>

      <div v-else class="no-result">
        <p>未找到检测结果，请先上传影像进行检测</p>
        <Button variant="primary" @click="handleBackToUpload">
          返回上传
        </Button>
      </div>
    </Card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import Card from '@/components/common/Card.vue'
import Button from '@/components/common/Button.vue'
import { taskManager } from '@/services/taskManager'

interface CenterPoint {
  x: number
  y: number
  area: number
}

interface DetectionResult {
  status: string
  message: string
  image_path: string
  image_shape: [number, number, number]
  n_clusters: number
  n_candidates: number
  method: string
  description: string
  center_points: CenterPoint[]
  note: string
}

const router = useRouter()
const detectionResult = ref<DetectionResult | null>(null)

onMounted(() => {
  // Try task manager first
  const task = taskManager.getCurrentTask()
  if (task?.type === 'unsupervised' && task.status === 'completed') {
    detectionResult.value = task.result
  } else {
    // Fallback to sessionStorage (backward compatibility)
    const resultStr = sessionStorage.getItem('detectionResult')
    if (resultStr) {
      detectionResult.value = JSON.parse(resultStr)
    }
  }
})

const handleExportGeoJSON = () => {
  if (!detectionResult.value) return

  const features = detectionResult.value.center_points.map((point, index) => ({
    type: 'Feature',
    properties: {
      id: index + 1,
      area: point.area,
      method: detectionResult.value!.method,
    },
    geometry: {
      type: 'Point',
      coordinates: [point.x, point.y],
    },
  }))

  const geojson = {
    type: 'FeatureCollection',
    features,
  }

  const dataStr = JSON.stringify(geojson, null, 2)
  const dataBlob = new Blob([dataStr], { type: 'application/json' })
  const url = URL.createObjectURL(dataBlob)
  const link = document.createElement('a')
  link.href = url
  link.download = 'disease_candidates.geojson'
  link.click()
  URL.revokeObjectURL(url)
}

const handleBackToUpload = () => {
  sessionStorage.removeItem('detectionResult')
  router.push('/unsupervised/upload')
}
</script>

<style scoped>
.unsupervised-result-page {
  display: flex;
  justify-content: center;
  padding: 24px;
}

.result-card {
  width: 100%;
  max-width: 800px;
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

.result-content {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.result-summary {
  background-color: #f9f9f9;
  padding: 16px;
  border-radius: 8px;
}

.summary-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin: 0 0 12px 0;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
}

.summary-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.summary-label {
  font-size: 12px;
  color: #999;
  font-weight: 500;
}

.summary-value {
  font-size: 16px;
  font-weight: 600;
  color: #0066cc;
}

.method-description {
  background-color: #f0f9ff;
  border-left: 4px solid #0066cc;
  padding: 16px;
  border-radius: 8px;
}

.description-title {
  font-size: 14px;
  font-weight: 600;
  color: #0066cc;
  margin: 0 0 8px 0;
}

.description-text {
  font-size: 13px;
  color: #333;
  margin: 0 0 12px 0;
  line-height: 1.5;
}

.warning-box {
  background-color: #fff5f5;
  border-left: 4px solid #ff9500;
  padding: 12px;
  border-radius: 4px;
  margin-top: 12px;
}

.warning-text {
  font-size: 12px;
  color: #ff6b00;
  margin: 0;
  line-height: 1.5;
}

.center-points-section {
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 16px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin: 0 0 12px 0;
}

.points-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 400px;
  overflow-y: auto;
}

.point-item {
  display: flex;
  align-items: center;
  padding: 12px;
  background-color: #f9f9f9;
  border-radius: 6px;
  border-left: 3px solid #0066cc;
}

.point-info {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
}

.point-index {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  background-color: #0066cc;
  color: white;
  border-radius: 50%;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}

.point-details {
  flex: 1;
}

.point-coord {
  font-size: 13px;
  color: #333;
  margin: 0 0 4px 0;
  font-weight: 500;
}

.point-area {
  font-size: 12px;
  color: #999;
  margin: 0;
}

.no-points {
  text-align: center;
  padding: 24px;
  color: #999;
  font-size: 14px;
}

.no-result {
  text-align: center;
  padding: 40px 20px;
}

.no-result p {
  font-size: 14px;
  color: #999;
  margin-bottom: 16px;
}

.action-buttons {
  display: flex;
  gap: 12px;
}

.action-buttons button {
  flex: 1;
}
</style>
