<template>
  <div class="history-page">
    <div class="history-container">
      <Card class="section-card">
        <div class="section-header">
          <h2>历史训练任务</h2>
        </div>

        <div v-if="trainingTasks.length > 0" class="tasks-list">
          <div v-for="task in trainingTasks" :key="task.id" class="task-card">
            <div class="task-header">
              <h3 class="task-name">{{ task.name }}</h3>
              <span class="task-status" :class="task.status">{{ formatStatus(task.status) }}</span>
            </div>
            <div class="task-info">
              <p><span class="label">创建时间：</span><span class="value">{{ formatDate(task.createdAt) }}</span></p>
              <p><span class="label">更新时间：</span><span class="value">{{ formatDate(task.updatedAt) }}</span></p>
            </div>
            <div class="task-actions">
              <Button variant="secondary" @click="viewTaskDetail(task.id)">
                查看详情
              </Button>
              <Button variant="secondary" @click="exportTask(task.id)">
                导出结果
              </Button>
            </div>
          </div>
        </div>
        <div v-else class="empty-state">
          <p>暂无训练任务</p>
        </div>
      </Card>

      <Card class="section-card">
        <div class="section-header">
          <h2>历史检测任务</h2>
        </div>

        <div v-if="detectionTasks.length > 0" class="tasks-list">
          <div v-for="task in detectionTasks" :key="task.id" class="task-card">
            <div class="task-header">
              <h3 class="task-name">{{ task.name }}</h3>
              <span class="task-status" :class="task.status">{{ formatStatus(task.status) }}</span>
            </div>
            <div class="task-info">
              <p><span class="label">创建时间：</span><span class="value">{{ formatDate(task.createdAt) }}</span></p>
              <p><span class="label">更新时间：</span><span class="value">{{ formatDate(task.updatedAt) }}</span></p>
            </div>
            <div class="task-actions">
              <Button variant="secondary" @click="viewTaskDetail(task.id)">
                查看详情
              </Button>
              <Button variant="secondary" @click="exportTask(task.id)">
                导出结果
              </Button>
            </div>
          </div>
        </div>
        <div v-else class="empty-state">
          <p>暂无检测任务</p>
        </div>
      </Card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import Card from '@/components/common/Card.vue'
import Button from '@/components/common/Button.vue'
import type { TrainingTask, DetectionTask } from '@/types'
import { apiClient } from '@/services/api'
import { userStore } from '@/services/userStore'

const trainingTasks = ref<TrainingTask[]>([])
const detectionTasks = ref<DetectionTask[]>([])
const isLoading = ref(false)
const error = ref('')

/**
 * 加载训练历史
 */
const loadTrainingHistory = async () => {
  try {
    const userId = userStore.getUserId()
    if (!userId) {
      console.warn('用户未登录，无法加载训练历史')
      return
    }

    const response = await apiClient.get(`/history/training/${userId}`)

    if (response.success && response.data) {
      // 映射后端数据到前端格式
      trainingTasks.value = response.data.map((task: any) => ({
        id: task.id.toString(),
        name: task.task_name,
        status: task.status,
        createdAt: formatDate(task.created_at),
        updatedAt: task.completed_at ? formatDate(task.completed_at) : formatDate(task.created_at),
      }))
    }
  } catch (e: any) {
    console.error('加载训练历史失败:', e)
    error.value = '加载训练历史失败'
  }
}

/**
 * 加载检测历史
 */
const loadDetectionHistory = async () => {
  try {
    const userId = userStore.getUserId()
    if (!userId) {
      console.warn('用户未登录，无法加载检测历史')
      return
    }

    const response = await apiClient.get(`/history/detection/${userId}`)

    if (response.success && response.data) {
      // 映射后端数据到前端格式
      detectionTasks.value = response.data.map((task: any) => ({
        id: task.id.toString(),
        name: task.task_name,
        status: task.status,
        createdAt: formatDate(task.created_at),
        updatedAt: task.completed_at ? formatDate(task.completed_at) : formatDate(task.created_at),
      }))
    }
  } catch (e: any) {
    console.error('加载检测历史失败:', e)
    error.value = '加载检测历史失败'
  }
}

const formatStatus = (status: string): string => {
  const statusMap: Record<string, string> = {
    pending: '待处理',
    running: '处理中',
    completed: '已完成',
    failed: '失败',
  }
  return statusMap[status] || status
}

const formatDate = (dateStr: string): string => {
  if (!dateStr) return ''

  try {
    const date = new Date(dateStr)
    const year = date.getFullYear()
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    const hours = String(date.getHours()).padStart(2, '0')
    const minutes = String(date.getMinutes()).padStart(2, '0')

    return `${year}-${month}-${day} ${hours}:${minutes}`
  } catch (e) {
    return dateStr
  }
}

const viewTaskDetail = (taskId: string) => {
  console.log('查看任务详情:', taskId)
}

const exportTask = (taskId: string) => {
  console.log('导出任务结果:', taskId)
}

onMounted(async () => {
  isLoading.value = true
  error.value = ''

  try {
    await Promise.all([
      loadTrainingHistory(),
      loadDetectionHistory()
    ])
  } catch (e) {
    console.error('加载历史任务失败:', e)
  } finally {
    isLoading.value = false
  }
})
</script>

<style scoped>
.history-page {
  display: flex;
  justify-content: center;
  padding: 24px;
}

.history-container {
  width: 100%;
  max-width: 900px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.section-card {
  width: 100%;
}

.section-header {
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid #f0f0f0;
}

.section-header h2 {
  font-size: 18px;
  font-weight: 600;
  color: #333;
  margin: 0;
}

.tasks-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.task-card {
  padding: 16px;
  background-color: #f9f9f9;
  border-radius: 8px;
  transition: all 0.2s;
}

.task-card:hover {
  background-color: #f5f5f5;
}

.task-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.task-name {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin: 0;
}

.task-status {
  font-size: 12px;
  padding: 4px 12px;
  border-radius: 4px;
  font-weight: 500;
}

.task-status.completed {
  background-color: #e8f5e9;
  color: #2e7d32;
}

.task-status.running {
  background-color: #fff3e0;
  color: #e65100;
}

.task-status.pending {
  background-color: #f3e5f5;
  color: #6a1b9a;
}

.task-status.failed {
  background-color: #ffebee;
  color: #c62828;
}

.task-info {
  margin-bottom: 12px;
}

.task-info p {
  font-size: 13px;
  margin: 6px 0;
  display: flex;
  justify-content: space-between;
}

.label {
  color: #999;
  font-weight: 500;
}

.value {
  color: #666;
  font-family: 'Monaco', 'Courier New', monospace;
}

.task-actions {
  display: flex;
  gap: 8px;
}

.task-actions button {
  flex: 1;
}

.empty-state {
  text-align: center;
  padding: 40px 20px;
  color: #999;
}

.empty-state p {
  font-size: 14px;
  margin: 0;
}
</style>
