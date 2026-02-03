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

const trainingTasks = ref<TrainingTask[]>([
  {
    id: '1',
    name: '训练任务 - 2024年样本集',
    status: 'completed',
    createdAt: '2024-01-15 10:30',
    updatedAt: '2024-01-15 14:45',
  },
  {
    id: '2',
    name: '训练任务 - 2023年样本集',
    status: 'completed',
    createdAt: '2024-01-10 09:00',
    updatedAt: '2024-01-10 12:30',
  },
])

const detectionTasks = ref<DetectionTask[]>([
  {
    id: '1',
    name: '检测任务 - 区域A',
    status: 'completed',
    createdAt: '2024-01-20 11:00',
    updatedAt: '2024-01-20 11:45',
  },
  {
    id: '2',
    name: '检测任务 - 区域B',
    status: 'completed',
    createdAt: '2024-01-18 14:30',
    updatedAt: '2024-01-18 15:20',
  },
])

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
  return dateStr
}

const viewTaskDetail = (taskId: string) => {
  console.log('查看任务详情:', taskId)
}

const exportTask = (taskId: string) => {
  console.log('导出任务结果:', taskId)
}

onMounted(() => {
  // 可以在这里加载历史任务数据
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
