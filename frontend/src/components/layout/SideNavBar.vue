<template>
  <aside class="side-nav-bar">
    <nav class="nav-groups">
      <div class="nav-group">
        <h3 class="group-title">训练流程</h3>
        <ul class="nav-items">
          <li v-for="item in trainingItems" :key="item.path">
            <router-link
              :to="item.path"
              :class="['nav-link', { active: isActive(item.path) }]"
            >
              {{ item.label }}
            </router-link>
          </li>
        </ul>
      </div>

      <div class="nav-group">
        <h3 class="group-title">检测流程</h3>
        <ul class="nav-items">
          <li v-for="item in detectionItems" :key="item.path">
            <router-link
              :to="item.path"
              :class="['nav-link', { active: isActive(item.path) }]"
            >
              {{ item.label }}
            </router-link>
          </li>
        </ul>
      </div>

      <div class="nav-group">
        <h3 class="group-title">非监督分类</h3>
        <ul class="nav-items">
          <li v-for="item in unsupervisedItems" :key="item.path">
            <router-link
              :to="item.path"
              :class="['nav-link', { active: isActive(item.path) }]"
            >
              {{ item.label }}
            </router-link>
          </li>
        </ul>
      </div>

      <div class="nav-group">
        <h3 class="group-title">任务管理</h3>
        <ul class="nav-items">
          <li>
            <router-link
              to="/task-progress"
              :class="['nav-link', { active: isActive('/task-progress') }]"
            >
              任务进度
            </router-link>
          </li>
        </ul>
      </div>

      <div class="nav-group">
        <h3 class="group-title">人工交互与历史</h3>
        <ul class="nav-items">
          <li>
            <router-link
              to="/history"
              :class="['nav-link', { active: isActive('/history') }]"
            >
              历史任务管理
            </router-link>
          </li>
        </ul>
      </div>
    </nav>
  </aside>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const trainingItems = [
  { path: '/training/upload', label: '训练样本上传' },
  { path: '/training/preprocess', label: '样本构建与预处理' },
  { path: '/training/model-config', label: '模型构建与参数配置' },
  { path: '/training/training', label: '模型训练' },
]

const detectionItems = [
  { path: '/detection/config-selection', label: '选择模型参数配置' },
  { path: '/detection/upload', label: '待检测影像上传' },
  { path: '/detection/result', label: '检测结果展示' },
  { path: '/detection/geojson', label: 'GeoJSON 修正与回流' },
]

const unsupervisedItems = [
  { path: '/unsupervised/upload', label: '非监督分类' },
  { path: '/unsupervised/result', label: '检测结果' },
]

const isActive = (path: string) => {
  return route.path === path
}
</script>

<style scoped>
.side-nav-bar {
  width: 240px;
  background-color: #ffffff;
  border-right: 1px solid #f0f0f0;
  overflow-y: auto;
  padding: 16px;
}

.nav-groups {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.nav-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.group-title {
  font-size: 12px;
  font-weight: 600;
  color: #999;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
}

.nav-items {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.nav-link {
  display: block;
  padding: 10px 12px;
  border-radius: 8px;
  color: #666;
  font-size: 14px;
  transition: all 0.2s;
}

.nav-link:hover {
  background-color: #f5f5f5;
  color: #333;
}

.nav-link.active {
  background-color: #e8f4ff;
  color: #0066cc;
  font-weight: 500;
}
</style>
